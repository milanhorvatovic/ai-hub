# bash — scaffold templates

Shapes to fill in from what the scan found. Placeholders in angle brackets are values the scan already established — and for this language the most important of them is the file list, which comes from the inventory rather than from a glob.

## `.shellcheckrc` — only when a finding needs one

**A repository with no `.shellcheckrc` is not missing anything.** `shellcheck`'s defaults are the floor, no audit rule produces a missing-config finding, and scaffolding a file to hold settings nobody asked for changes how the tool resolves sources for a repository whose only finding was that the linter did not run. Close that finding with the CI step; leave the config absent.

Where a concrete finding does need a setting — a repository whose scripts source each other and whose report is dominated by unfollowed-source warnings — write only that setting, with the reason beside it:

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
[*.{sh,bash}]
indent_style = <the project's existing style>
indent_size = <the project's existing width>
switch_case_indent = true

# One section per extensionless path the inventory found; EditorConfig matches
# on path patterns, so these cannot be folded into the glob above.
[{.githooks/*,bin/deploy,bin/release}]
indent_style = <the project's existing style>
indent_size = <the project's existing width>
switch_case_indent = true
```

The indentation values come from the scripts the inventory found, not from a default: picking a width would reformat every line of every script for a repository whose finding was that nothing formatted them at all. `switch_case_indent` is the `-ci` flag spelled as a setting, and it is here because the floor names it. `binary_next_line` — `-bn` — is deliberately absent: the floor does not ask for it, and it reflows every continued command in the repository, which is a large unrequested diff handed to someone who asked for a config file. Carry it over only where the scan found `shfmt` already invoked with `-bn`. The same rule governs the rest: when the repository already invokes `shfmt` with flags somewhere, translate the flags it uses rather than imposing these.

Where the inventory's extensionless paths are too many or too scattered to enumerate, the honest alternative is to skip `.editorconfig` for them and pass one explicit flag set to every `shfmt` invocation instead. That loses the editor half of the deal and should be said out loud; what it does not do is leave half the repository formatted by a policy nobody chose.

## Finding the files to check

The list comes from the inventory, not a glob. This is the shape that reaches the scripts a `*.sh` pattern misses:

```bash
#!/usr/bin/env bash
set -euo pipefail

# Every tracked file, classified once: the shebang decides, and only a file
# without one falls back to its extension.
git ls-files -z | tr '\0' '\n' |
  while IFS= read -r f; do
    [ -f "$f" ] || continue
    first=$(head -n 1 -- "$f")
    case "$first" in
      '#!'*)
        if printf '%s\n' "$first" | grep -Eq '[/ ](sh|bash|dash|ksh|oksh|bats)([[:space:]]|$)'; then
          printf '%s\n' "$f"
        fi
        ;;
      *)
        case "$f" in
          *.sh | *.bash) printf '%s\n' "$f" ;;
        esac
        ;;
    esac
  done | sort -u
```

One pass, not two. An earlier shape emitted every `*.sh` and `*.bash` file directly and ran the shebang test only over the rest, which meant a zsh script named `deploy.sh` went straight into the list the generated job feeds to `shellcheck` — the unsupported-shell failure this section promises to keep out, arriving through the branch that never checked. The shebang is the authority wherever there is one; the extension answers only for a file that declares nothing, and `shellcheck` reads those as `sh`, which is the right default.

The interpreter list is what `shellcheck` actually accepts, established by running it rather than by reading its error message: `sh`, `bash`, `dash`, `ksh`, `oksh`, and `bats` exit clean, while `mksh`, `ash`, and `zsh` do not. Both directions of getting this list wrong cost something. Too narrow — matching only the two spellings of Bash — silently drops `#!/bin/dash` and `#!/bin/ksh` scripts, reproducing the coverage under-reach this capability exists to find. Too wide is worse, because the extra file does not go unchecked, it turns the job red: `zsh` raises `SC1071`, `mksh` raises `SC1008`, and neither is a lint result the scaffold can act on.

`ash` is the interesting exclusion. `shellcheck` checks it — as Dash — but warns `SC2187` while doing so and exits non-zero, so an un-annotated ash script reddens the job just as surely as an unsupported one. Its fix is a directive rather than a removal: `# shellcheck shell=dash` at the top of the file silences the warning and keeps the script checked.

Report the shells left out — `mksh`, `ash`, `zsh` — by name as outside the generated job's reach, with ash's directive named as its remedy. Dropping them silently, or feeding them to a tool that will refuse them, are the two failures this list exists between.

Two more details in that loop are load-bearing, and both were found by running it rather than by reading it. No `mapfile`: it arrived in Bash 4 and macOS still ships 3.2 as `/bin/bash`, so a discovery script using it fails on the machines of the contributors most likely to run it by hand — and this one is written to be run by hand and read before anything is wired to it. A pipeline into `sort -u` needs no array at all.

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
        cd "$RUNNER_TEMP"
        curl -fsSLO "https://github.com/koalaman/shellcheck/releases/download/v<pinned>/shellcheck-v<pinned>.linux.x86_64.tar.xz"
        curl -fsSLo shfmt "https://github.com/mvdan/sh/releases/download/v<pinned>/shfmt_v<pinned>_linux_amd64"
        printf '%s  %s\n' "<shellcheck sha256>" "shellcheck-v<pinned>.linux.x86_64.tar.xz" > sums
        printf '%s  %s\n' "<shfmt sha256>" "shfmt" >> sums
        sha256sum -c sums
        tar -xJf "shellcheck-v<pinned>.linux.x86_64.tar.xz" -C bin --strip-components=1 "shellcheck-v<pinned>/shellcheck"
        install -m 0755 shfmt bin/shfmt
        echo "$RUNNER_TEMP/bin" >> "$GITHUB_PATH"
    - name: shellcheck
      run: |
        shopt -s globstar
        shellcheck <the inventory's files, or the discovery command above>
    - name: shfmt
      run: shfmt -d <the same file list>
```

Both downloads are checksum-verified before anything is extracted or made executable, and the digests are recorded here rather than fetched alongside the artifact. A version tag is not an identity: a release asset can be replaced without its URL changing, so a pinned version alone leaves the job executing whatever is behind that link today. The version pins which release the job wants; the digest is what makes the job refuse a different one. Fetching the checksums from the same host at the same time would verify only that the download was not corrupted in transit, which is not the question.

The binaries land in a runner-writable directory and reach the later steps through `GITHUB_PATH`, rather than being written straight into a system path. A job runs as an unprivileged user, so a scaffold that assumes it can write to `/usr/local/bin` risks failing before either check runs — and failing in the install step, where the error says nothing about shell linting.

`shfmt` is the reason this job needs an install step at all. `shellcheck` is preinstalled on the common hosted Ubuntu images and `shfmt` is not, so a job that assumes both fails on a fresh runner with `shfmt: command not found` — a scaffold that cannot run is worse than the gap it closes. A pinned setup action for either tool works equally well; the point is that both arrive deliberately.

Pinning both versions here is what keeps the scaffold consistent with what the router promises and with the scaffold contract that an addressed row re-audits clean. Taking `shellcheck` from the image is the cheaper-looking option and it is the one that produces a `floating` finding on the very next run — prescribing a shape the audit then reports is the contradiction this skill has now made six times, and there is no reason to make it a seventh when the install step already exists for `shfmt`.

`shfmt -d` prints a diff and exits non-zero when a file would change, which is the check-mode behavior; `shfmt -w` writes, and belongs nowhere near CI.

Hooks are the case worth being explicit about. If the inventory found `.githooks/` or `.husky/`, they are in the list — they run on every commit on every contributor's machine, which makes them the shell in the repository with the widest blast radius and, almost always, the least review.
