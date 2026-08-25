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

The extension glob carries every extension the inventory collects, `.bats` included — the discovery script emits those files and the `shfmt` step below formats them, so leaving them out of this section hands them the tool's defaults while every other script follows the project's policy. That is the same split this section exists to prevent, arriving through the extension nobody remembered to add.

The section headers come from the inventory, not from `*.sh`. This is the same trap as the linter's file list: the scan exists to find the shell that no extension glob matches, and a config keyed only to `[*.sh]` then formats the hooks and `bin/` scripts with `shfmt`'s defaults instead — one repository, two formatting policies, and the files with the widest blast radius on the wrong one.

```ini
[*.{sh,bash,bats}]
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
# without one falls back to its extension. NUL in, NUL out.
#
# The accepted dialects are an argument, not a constant: the two tools this
# feeds do not support the same shells, so each caller passes its own set.
accepted=${1:?pass a shebang alternation, e.g. 'sh|bash|dash|ksh|oksh|bats|ash|busybox[[:space:]]+sh'}

git ls-files -z |
  while IFS= read -r -d '' f; do
    # A symlink is never read: a tracked link can point anywhere the runner can
    # reach, and the tools this list feeds would open the target, not the repo.
    [ -L "$f" ] && continue
    [ -f "$f" ] || continue
    # Bounded: a shebang cannot be long, and a tracked minified bundle or binary
    # with no newline would otherwise make "the first line" the whole file.
    first=$(head -c 256 -- "$f" | head -n 1)
    case "$first" in
      '#!'*)
        # `env` may front a single-token interpreter, but not `busybox sh`:
        # shellcheck takes that only when the binary is named directly.
        if printf '%s\n' "$first" |
          grep -Eq "^#![[:space:]]*(/[^[:space:]]*/)?(env([[:space:]]+-S)?[[:space:]]+)?($accepted)([[:space:]]|\$)" &&
          ! printf '%s\n' "$first" |
            grep -Eq "^#![[:space:]]*(/[^[:space:]]*/)?env([[:space:]]+-S)?[[:space:]]+busybox"; then
          printf '%s\0' "$f"
        fi
        ;;
      *)
        # No shebang: the extension implies a dialect, and that dialect faces
        # the same accepted-set filter the shebang branch applies.
        case "$f" in
          *.sh) implied=sh ;;
          *.bash) implied=bash ;;
          *.bats) implied=bats ;;
          *) continue ;;
        esac
        if printf '%s\n' "$implied" | grep -Eq "^($accepted)$"; then
          printf '%s\0' "$f"
        fi
        ;;
    esac
  done
```

The trigger and the permission floor are part of the scaffold, not context around it. A bare job fragment dropped into a push-only workflow still grades `wiring` on the next audit — it runs, and not where review happens — so a scaffold that omitted `on: pull_request` would not close the finding it was written for. And a job that runs repository code inherits whatever token permissions the repository defaults to, which on an older repository is write; `contents: read` is the floor, raised only for a scope the job demonstrably needs.

The `--` before the appended paths is not decoration. A tracked file may legally be named `-deploy.sh`, and `xargs` appends it as an argument like any other, so the tool reads it as a bundle of options and reports an unrecognized option — the job then fails on a filename rather than on a script. The terminator was checked against `shellcheck` directly; `shfmt` takes it by the same convention, which is stated here rather than claimed as tested.

NUL delimiters end to end, because a path is not a line. Git emits `-z` for a reason: a filename may legally contain a newline, and converting to newlines on the way in splits one such path into two bogus entries — then hands them to a linter as two files that do not exist. Reading with `read -d ''` and emitting with a trailing NUL keeps the list usable as arguments, which is what the CI step below consumes it as.

One pass, not two. An earlier shape emitted every `*.sh` and `*.bash` file directly and ran the shebang test only over the rest, which meant a zsh script named `deploy.sh` went straight into the list the generated job feeds to `shellcheck` — the unsupported-shell failure this section promises to keep out, arriving through the branch that never checked. The shebang is the authority wherever there is one; the extension answers only for a file that declares nothing, and `shellcheck` reads those as `sh`, which is the right default.

The interpreter list is what `shellcheck` actually accepts, established by running it rather than by reading its error message: `sh`, `bash`, `dash`, `ksh`, `oksh`, and `bats` exit clean, while `mksh`, `ash`, and `zsh` do not. Both directions of getting this list wrong cost something. Too narrow — matching only the two spellings of Bash — silently drops `#!/bin/dash` and `#!/bin/ksh` scripts, reproducing the coverage under-reach this capability exists to find. Too wide is worse, because the extra file does not go unchecked, it turns the job red: `zsh` raises `SC1071`, `mksh` raises `SC1008`, and neither is a lint result the scaffold can act on.

`ash` belongs **in** the list, which took a measurement to settle. Left alone it exits non-zero with `SC2187` — and that diagnostic is a request rather than a refusal: it asks for `# shellcheck shell=dash` at the top of the file, and with the directive present the same file exits clean. Excluding ash therefore made its own documented remedy unreachable, because discovery dropped the file before `shellcheck` could read the directive it was asking for. Include it, and let the directive decide whether the job passes.

The second grep is what keeps that measurement honest. The optional `env` prefix in the first pattern applies to every alternative, so with `busybox sh` in the accepted set it would also admit `#!/usr/bin/env busybox sh` — the one spelling measured to raise `SC1008` — and the generated job would fail on a file this classifier was written to exclude. Rejecting the `env`-fronted form explicitly is cheaper than splitting the alternation into two shapes.

`busybox sh` is accepted too, and only by the spellings that name the binary directly — `#!/bin/busybox sh` and `#!/usr/bin/busybox sh` pass, while routing it through `env` raises `SC1008`. It is two tokens rather than one, which is why the alternation carries a whitespace class rather than a plain name.

Report the shells left out — `mksh` and `zsh`, both refused outright — by name as outside the generated job's reach. Dropping them silently, or feeding them to a tool that will refuse them, are the two failures this list exists between.

The pattern is anchored to the **interpreter's own position** rather than searching the line. A leading `.*` looks harmless and is not: it lets the match slide past the real interpreter to any later word, so `#!/usr/bin/env -S python -m bash` and `#!/usr/bin/python3 -c import bash` both read as shell and the generated job hands a Python file to a shell linter, which then fails for a reason that has nothing to do with the repository's shell. The path, the optional `env`, and the interpreter are matched in sequence instead.

The `env -S` segment is optional in the pattern because it is not optional in practice: `#!/usr/bin/env -S bash -e` is the standard way to pass a flag through `env`, and a classifier that only accepted the interpreter directly after a slash would drop every script written that way — silently, from both generated tool invocations, which is the failure this inventory exists to prevent.

The extension branch runs the **same** accepted-set filter as the shebang branch, which is the point of taking the dialects as an argument at all. An earlier shape emitted every known extension unconditionally, so the two per-tool lists changed nothing for files without a shebang: a `.bats` file went to a formatter whose pinned version might not accept `bats`, and the generated job failed on a file the caller had deliberately excluded. Mapping each extension to the dialect it implies puts both branches under one rule.

`.bats` is in the extension fallback because Bats files legitimately carry no shebang: the runner supplies the interpreter, so the shebang branch never sees them and an extension list of `.sh` and `.bash` alone leaves a repository's whole test suite unchecked.

**Two tools, two lists, which is why the script takes its dialects as an argument — and both lists are placeholders because they belong to a version rather than to this file.** Their support differs and it moves between releases, so a set written here as fact would be wrong for somebody's pinned version and wrong silently: a dialect wrongly included reaches a tool that refuses it and reddens the job, and one wrongly excluded leaves those scripts outside the check while the job stays green.

Establishing each set is a step for the **user**, not for this skill, which does not run the tools it audits. Hand the commands over with the scaffold and leave the placeholders for the answers, on the versions the repository pins rather than whatever is installed where the audit ran — that would answer about a different computer.

One trap in doing it, and it is easy to walk into: the two questions live in different namespaces. The script matches **shebang executable names** — `sh`, `dash`, `bash` — while a formatter's help output lists **parser dialect labels**, which are not the same vocabulary and do not map one to one; a label like `posix` describes a grammar that several executables select. Copying help output straight into the alternation therefore drops ordinary `#!/bin/sh` and `#!/bin/dash` scripts, silently, which is the coverage failure this inventory exists to prevent. Ask the right question of each tool: which **shebang names** does this version accept, and route to a supported grammar. `shellcheck` answers it directly, because it names the shells it takes in the error it raises when handed one it does not.

What was measured here, against `shellcheck` 0.11: `sh`, `bash`, `dash`, `ksh`, `oksh`, `bats`, and `busybox sh` named by a direct path all exit clean; `ash` exits non-zero with `SC2187` until the file carries `# shellcheck shell=dash`, after which it exits clean; `mksh` raises `SC1008`, `zsh` raises `SC1071`, and `busybox sh` routed through `env` raises `SC1008`. `shfmt` was **not** measured — it is not installed where this was written — so its set is deliberately left for the adopter to read off `--help` rather than asserted from memory. A reviewer of this template reported that current `shfmt` handles `zsh`, which is plausible and which nothing here can confirm; that is precisely why the value is a placeholder and not a list.

Two more details in that loop are load-bearing, and both were found by running it rather than by reading it. No `mapfile`: it arrived in Bash 4 and macOS still ships 3.2 as `/bin/bash`, so a discovery script using it fails on the machines of the contributors most likely to run it by hand — and this one is written to be run by hand and read before anything is wired to it. A pipeline into `sort -u` needs no array at all.

And the shebang test is an `if` rather than `cmd && printf`. With `&&`, the last file examined decides the loop's exit status, so a script that printed a correct list would still exit non-zero whenever the final tracked file was not shell — which under `set -e`, or as a CI step, is a failure on a run that worked.

Symlinks are dropped before anything is read, and `[ -f ]` alone does not do that — it follows the link and answers about the target. A pull request can add a tracked `deploy.sh` pointing at a file outside the checkout, and the list this produces is fed straight to `shellcheck` and `shfmt`, which would open whatever it names on the runner. Rejecting links costs a line and closes that.

The first-line read is capped at a couple of hundred bytes because a shebang cannot exceed that and a repository can contain files that are one enormous line. A tracked minified bundle with no trailing newline turns an unbounded `head -n 1` into a read of the entire file, per file, to inspect two bytes — measured here at five million characters against a hundred and twenty-eight for the bounded form.

Tracked files only, and the reason is the CI step this feeds. An untracked script exists on the machine that ran the discovery and nowhere else, so copying it into a workflow's file list produces a job that fails on a path absent from the checkout — a scaffold that works for its author and for no one else. `git ls-files` is also what makes the shebang pass finite: it walks what the repository contains rather than everything under the working directory, so ignored build output and vendored trees never reach the `head` check.

Run it once and read the output before wiring it into CI. The list is the audit's evidence, and a maintainer looking at it will spot both a missing script and a wrongly included one faster than any heuristic here can.

## The CI step

```yaml
on:
  pull_request:
  push:
    branches: [<the default branch>]

permissions:
  contents: read

jobs:
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
        run: <discovery> '<shellcheck dialects>' | xargs -0 --no-run-if-empty shellcheck --
      - name: shfmt
        run: <discovery> '<shfmt dialects>' | xargs -0 --no-run-if-empty shfmt -d --
```

Both downloads are checksum-verified before anything is extracted or made executable, and the digests are recorded here rather than fetched alongside the artifact. A version tag is not an identity: a release asset can be replaced without its URL changing, so a pinned version alone leaves the job executing whatever is behind that link today. The version pins which release the job wants; the digest is what makes the job refuse a different one. Fetching the checksums from the same host at the same time would verify only that the download was not corrupted in transit, which is not the question.

The binaries land in a runner-writable directory and reach the later steps through `GITHUB_PATH`, rather than being written straight into a system path. A job runs as an unprivileged user, so a scaffold that assumes it can write to `/usr/local/bin` risks failing before either check runs — and failing in the install step, where the error says nothing about shell linting.

`shfmt` is the reason this job needs an install step at all. `shellcheck` is preinstalled on the common hosted Ubuntu images and `shfmt` is not, so a job that assumes both fails on a fresh runner with `shfmt: command not found` — a scaffold that cannot run is worse than the gap it closes. A pinned setup action for either tool works equally well; the point is that both arrive deliberately.

Pinning both versions here is what keeps the scaffold consistent with what the router promises and with the scaffold contract that an addressed row re-audits clean. Taking `shellcheck` from the image is the cheaper-looking option and it is the one that produces a `floating` finding on the very next run — prescribing a shape the audit then reports is the contradiction this skill has now made six times, and there is no reason to make it a seventh when the install step already exists for `shfmt`.

`shfmt -d` prints a diff and exits non-zero when a file would change, which is the check-mode behavior; `shfmt -w` writes, and belongs nowhere near CI.

Hooks are the case worth being explicit about. If the inventory found `.githooks/` or `.husky/`, they are in the list, because an unlinted script is worth linting whether or not it currently runs. Their blast radius is conditional rather than given: a hook directory activated by `core.hooksPath` or an installer runs on every commit on every machine that ran the setup, and one nobody has wired runs nowhere. Say which of those the repository looks like rather than assuming the first — presenting an inert directory as active execution is the same conflation the audit is built to avoid.
