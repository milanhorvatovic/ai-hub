# bash — scaffold templates

Shapes to fill in from what the scan found. Placeholders in angle brackets are values the scan already established — and for this language the most important of them is the file list, which comes from the inventory rather than from a glob.

## `.shellcheckrc`

```ini
# Follow sourced files rather than warning about them; source paths are
# relative to the invocation, so keep CI and local invocations in one place.
external-sources=true
```

**No `shell=` line.** It reads like a fallback for files without a shebang and is not one: it overrides shebang detection for every file checked, so on a repository holding both `sh` and Bash scripts it silently grades the portable ones by Bash's rules — the exact dialect conflict this capability's audit reports, created by its own scaffold. Shebangs already declare the dialect per file, and they declare it where the script runs rather than only where it is linted. Set `shell=` only for a repository whose scripts genuinely all share one dialect and whose shebangs are missing, and say why in a comment when you do.

Do not scaffold a `disable=` line here. A repository-wide suppression turns off a check for every script including the ones written next year, and the floor's position is that a suppression carries a one-line reason at the site it applies to. Where an audit found a rule that genuinely does not fit the repository, propose the per-file directive with its reason instead:

```bash
# shellcheck disable=SC2086  # word splitting is intended: $FLAGS carries multiple args
run_tool $FLAGS
```

## `shfmt` settings in `.editorconfig`

`shfmt` reads `.editorconfig`, which is also what a contributor's editor reads — one declaration for both, instead of flags that live only in a CI step.

The section headers come from the inventory, not from `*.sh`. This is the same trap as the linter's file list: the scan exists to find the shell that no extension glob matches, and a config keyed only to `[*.sh]` then formats the hooks and `bin/` scripts with `shfmt`'s defaults instead — one repository, two formatting policies, and the files with the widest blast radius on the wrong one.

```ini
[*.sh]
indent_style = space
indent_size = 2
switch_case_indent = true
binary_next_line = true

# One section per extensionless path the inventory found; EditorConfig matches
# on path patterns, so these cannot be folded into the glob above.
[{.githooks/*,bin/deploy,bin/release}]
indent_style = space
indent_size = 2
switch_case_indent = true
binary_next_line = true
```

`switch_case_indent` and `binary_next_line` are the `-ci` and `-bn` flags spelled as settings. When the repository already invokes `shfmt` with flags somewhere, translate the flags it uses rather than imposing these — a reformat of every script is a large diff to hand someone who asked for a config file.

Where the inventory's extensionless paths are too many or too scattered to enumerate, the honest alternative is to skip `.editorconfig` for them and pass one explicit flag set to every `shfmt` invocation instead. That loses the editor half of the deal and should be said out loud; what it does not do is leave half the repository formatted by a policy nobody chose.

## Finding the files to check

The list comes from the inventory, not a glob. This is the shape that reaches the scripts a `*.sh` pattern misses:

```bash
#!/usr/bin/env bash
set -euo pipefail

# Tracked files that are shell: by extension, or by shebang.
{
  git ls-files -z '*.sh' '*.bash' | tr '\0' '\n'
  git ls-files -z | tr '\0' '\n' |
    while IFS= read -r f; do
      [ -f "$f" ] || continue
      if head -n 1 -- "$f" | grep -Eq '^#!.*\b(ba)?sh\b'; then
        printf '%s\n' "$f"
      fi
    done
} | sort -u
```

Two details in that loop are load-bearing, and both were found by running it rather than by reading it. No `mapfile`: it arrived in Bash 4 and macOS still ships 3.2 as `/bin/bash`, so a discovery script using it fails on the machines of the contributors most likely to run it by hand — and this one is written to be run by hand and read before anything is wired to it. A pipeline into `sort -u` needs no array at all.

And the shebang test is an `if` rather than `cmd && printf`. With `&&`, the last file examined decides the loop's exit status, so a script that printed a correct list would still exit non-zero whenever the final tracked file was not shell — which under `set -e`, or as a CI step, is a failure on a run that worked.

Tracked files only, and the reason is the CI step this feeds. An untracked script exists on the machine that ran the discovery and nowhere else, so copying it into a workflow's file list produces a job that fails on a path absent from the checkout — a scaffold that works for its author and for no one else. `git ls-files` is also what makes the shebang pass finite: it walks what the repository contains rather than everything under the working directory, so ignored build output and vendored trees never reach the `head` check.

Run it once and read the output before wiring it into CI. The list is the audit's evidence, and a maintainer looking at it will spot both a missing script and a wrongly included one faster than any heuristic here can.

## The CI step

```yaml
shell:
  runs-on: ubuntu-latest
  steps:
    - uses: actions/checkout@<40-char-sha> # <the version this sha is>
    - name: install shellcheck and shfmt
      run: |
        mkdir -p "$RUNNER_TEMP/bin"
        curl -fsSL "https://github.com/koalaman/shellcheck/releases/download/v<pinned>/shellcheck-v<pinned>.linux.x86_64.tar.xz" \
          | tar -xJ -C "$RUNNER_TEMP/bin" --strip-components=1 "shellcheck-v<pinned>/shellcheck"
        curl -fsSL -o "$RUNNER_TEMP/bin/shfmt" \
          "https://github.com/mvdan/sh/releases/download/v<pinned>/shfmt_v<pinned>_linux_amd64"
        chmod +x "$RUNNER_TEMP/bin/shfmt"
        echo "$RUNNER_TEMP/bin" >> "$GITHUB_PATH"
    - name: shellcheck
      run: |
        shopt -s globstar
        shellcheck <the inventory's files, or the discovery command above>
    - name: shfmt
      run: shfmt -d <the same file list>
```

The binaries land in a runner-writable directory and reach the later steps through `GITHUB_PATH`, rather than being written straight into a system path. A job runs as an unprivileged user, so a scaffold that assumes it can write to `/usr/local/bin` risks failing before either check runs — and failing in the install step, where the error says nothing about shell linting.

`shfmt` is the reason this job needs an install step at all. `shellcheck` is preinstalled on the common hosted Ubuntu images and `shfmt` is not, so a job that assumes both fails on a fresh runner with `shfmt: command not found` — a scaffold that cannot run is worse than the gap it closes. A pinned setup action for either tool works equally well; the point is that both arrive deliberately.

Pinning both versions here is what keeps the scaffold consistent with what the router promises and with the scaffold contract that an addressed row re-audits clean. Taking `shellcheck` from the image is the cheaper-looking option and it is the one that produces a `floating` finding on the very next run — prescribing a shape the audit then reports is the contradiction this skill has now made six times, and there is no reason to make it a seventh when the install step already exists for `shfmt`.

`shfmt -d` prints a diff and exits non-zero when a file would change, which is the check-mode behavior; `shfmt -w` writes, and belongs nowhere near CI.

Hooks are the case worth being explicit about. If the inventory found `.githooks/` or `.husky/`, they are in the list — they run on every commit on every contributor's machine, which makes them the shell in the repository with the widest blast radius and, almost always, the least review.
