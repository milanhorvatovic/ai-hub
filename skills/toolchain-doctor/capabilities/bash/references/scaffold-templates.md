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
# Word splitting is intended here: $FLAGS carries several arguments.
# shellcheck disable=SC2086
run_tool $FLAGS
```

The reason sits on its own line immediately above the directive, which is the shape the rulebook these floors are shared with states, and a scaffold exists to hand a repository the house shape rather than a personal one. `shellcheck` honours a reason trailing the directive on one line just as well, so a repository already writing them that way is documented and is graded as such — the audit's row asks whether a reason is there, never where it sits. Prescribing one layout and grading another is deliberate here: a scaffold gets to have a preference, and an audit reporting on code someone else wrote does not.

## `shfmt` settings in `.editorconfig`

`shfmt` reads `.editorconfig`, which is also what a contributor's editor reads — one declaration for both, instead of flags that live only in a CI step.

The extension glob carries every extension the inventory collects, `.bats` included — the discovery script emits those files and the `shfmt` step below formats them, so leaving them out of this section hands them the tool's defaults while every other script follows the project's policy. That is the same split this section exists to prevent, arriving through the extension nobody remembered to add.

The section headers come from the inventory, not from `*.sh`. This is the same trap as the linter's file list: the scan exists to find the shell that no extension glob matches, and a config keyed only to `[*.sh]` then formats the hooks and `bin/` scripts with `shfmt`'s defaults instead — one repository, two formatting policies, and the files with the widest blast radius on the wrong one.

```ini
[*.{sh,bash,bats}]
indent_style = <the project's existing style>
indent_size = <the project's existing width>
switch_case_indent = <true if the scripts indent case bodies, false if not>

# One section per extensionless path the inventory classified as shell —
# EditorConfig matches on path patterns, so these cannot fold into the glob
# above, and each is an exact path, never a `.githooks/*` wildcard. The wildcard
# is the trap this section exists to avoid one directory in: a hook that is not
# shell, or one whose interpreter the scan could not establish, would take these
# formatting settings in every contributor's editor. List the paths the
# inventory returned and no others.
[{.githooks/pre-commit,.githooks/pre-push,bin/deploy,bin/release}]
indent_style = <the project's existing style>
indent_size = <the project's existing width>
switch_case_indent = <true if the scripts indent case bodies, false if not>
```

The indentation values come from the scripts the inventory found, not from a default: picking a width would reformat every line of every script for a repository whose finding was that nothing formatted them at all. `switch_case_indent` — the `-ci` flag spelled as a setting — is filled the same way, from what the scripts already do. The floor names `-ci` as the convention most projects follow, not as a bar it sets, so writing `true` into a repository that had deliberately left its `case` bodies flush reformats every one of them — the unrequested diff the width setting is careful to avoid, arriving through a line that looks like a default. Read it from the scan and write `false` where the scripts do not indent case bodies. `binary_next_line` — `-bn` — is deliberately absent: the floor does not ask for it, and it reflows every continued command in the repository, which is a large unrequested diff handed to someone who asked for a config file. Carry it over only where the scan found `shfmt` already invoked with `-bn`. The same rule governs the rest: when the repository already invokes `shfmt` with flags somewhere, translate the flags it uses rather than imposing these.

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

git ls-files -z \
  -- ':(exclude,glob)**/node_modules/**' ':(exclude,glob)**/vendor/**' \
     ':(exclude,glob)**/target/**' ':(exclude,glob)**/dist/**' \
     ':(exclude,glob)**/build/**' ':(exclude,glob)**/.venv/**' \
     ':(exclude,glob)**/venv/**' |
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
        # `env` may front a single-token interpreter, but not `busybox sh` —
        # that spelling is one the linter takes only from a direct path.
        if printf '%s\n' "$first" |
          grep -Eq "^#![[:space:]]*(/[^[:space:]]*/)?(env([[:space:]]+(-[^[:space:]]+|[A-Za-z_][A-Za-z0-9_]*=[^[:space:]]*))*[[:space:]]+)?($accepted)([[:space:]]|\$)" &&
          ! printf '%s\n' "$first" |
            grep -Eq "^#![[:space:]]*(/[^[:space:]]*/)?env([[:space:]]+(-[^[:space:]]+|[A-Za-z_][A-Za-z0-9_]*=[^[:space:]]*))*[[:space:]]+busybox"; then
          printf '%s\0' "$f"
        fi
        ;;
      *)
        # No shebang: the extension implies a dialect, and that dialect faces
        # the same accepted-set filter the shebang branch applies.
        case "$f" in
          .husky/_/*) continue ;;
          .husky/*) implied='sh' ;;
          *.sh) implied='sh' ;;
          *.bash) implied='bash' ;;
          *.bats) implied='bats' ;;
          *) continue ;;
        esac
        if printf '%s\n' "$implied" | grep -Eq "^($accepted)$"; then
          printf '%s\0' "$f"
        fi
        ;;
    esac
  done
```

The dialect names are quoted for the same tool rather than for style: `implied=sh` assigns a string that is also a command name, and `shellcheck` raises `SC2209` on it because the far more common intent behind that line is `implied=$(sh)`. The quotes say which one was meant. That one was invisible until the parse errors above were fixed — a script that will not parse is a script whose remaining findings nobody has seen.

No comment in that script begins with the linter's own name, and the phrasing is bent around the constraint rather than by taste: `shellcheck` reads `# shellcheck <word>` as a directive wherever it appears, so an ordinary sentence starting with the tool's name is parsed as one and raises `SC1072` — a parse error, on the script this capability hands a repository to wire its linting up with. This was found by running `shellcheck` over the block rather than by reading it, which is also why the suite now does that.

The exclusions are the mode contract's list of vendored and generated trees, applied here because `git ls-files` answers a different question than the inventory asks: it emits every tracked path, and a repository that commits its vendored dependencies gets their shell handed to `shellcheck` and `shfmt` as though it were its own. That produces findings a maintainer cannot act on, and a red job for code they did not write — the second being worse, because the scaffold was prescribed to close a finding rather than to open a new class of them. The `glob` magic is what makes each one reach past the top level: `:!vendor` excludes a root `vendor/` and leaves `packages/x/vendor/` in the list, which was confirmed by running both spellings against a repository holding each shape. Repositories that generate into some other directory add it here; the list is a floor rather than an inventory of every name a project might use.

A tracked file that also matches an ignore rule stays in, which is what the mode contract asks for and was not always: the contract read as though ignore rules excluded tracked source too, and the two rules disagreeing would have been worse than either, because stage 0 decides whether this lane loads at all. A repository whose only shell is a tracked, ignored script would never have reached the inventory written to keep it.

The trigger and the permission floor are part of the scaffold, not context around it. A bare job fragment dropped into a push-only workflow still grades `wiring` on the next audit — it runs, and not where review happens — so a scaffold that omitted `on: pull_request` would not close the finding it was written for. And a job that runs repository code inherits whatever token permissions the repository defaults to, which on an older repository is write; `contents: read` is the floor, raised only for a scope the job demonstrably needs.

The `--` before the appended paths is not decoration. A tracked file may legally be named `-deploy.sh`, and `xargs` appends it as an argument like any other, so the tool reads it as a bundle of options and reports an unrecognized option — the job then fails on a filename rather than on a script. The terminator was checked against `shellcheck` directly; `shfmt` takes it by the same convention, which is stated here rather than claimed as tested.

NUL delimiters end to end, because a path is not a line. Git emits `-z` for a reason: a filename may legally contain a newline, and converting to newlines on the way in splits one such path into two bogus entries — then hands them to a linter as two files that do not exist. Reading with `read -d ''` and emitting with a trailing NUL keeps the list usable as arguments, which is what the CI step below consumes it as.

One pass, not two. An earlier shape emitted every `*.sh` and `*.bash` file directly and ran the shebang test only over the rest, which meant a zsh script named `deploy.sh` went straight into the list the generated job feeds to `shellcheck` — the unsupported-shell failure this section promises to keep out, arriving through the branch that never checked. The shebang is the authority wherever there is one; the extension answers only for a file that declares nothing, and `shellcheck` reads those as `sh`, which is the right default.

The interpreter list is what `shellcheck` can be made to accept, established by running it rather than by reading its error message. Two questions live inside that and separating them is what settles the list: which shebangs exit clean as they stand — `sh`, `bash`, `dash`, `ksh`, `oksh`, and `bats` — and which of the rest can be made to, which is where `ash` parts company with `mksh` and `zsh` and why it is in the alternation, per the paragraph below. Both directions of getting this list wrong cost something. Too narrow — matching only the two spellings of Bash — silently drops `#!/bin/dash` and `#!/bin/ksh` scripts, reproducing the coverage under-reach this capability exists to find. Too wide is worse, because the extra file does not go unchecked, it turns the job red: `zsh` raises `SC1071`, `mksh` raises `SC1008`, and neither is a lint result the scaffold can act on.

`ash` belongs **in** the list, which took a measurement to settle. Left alone it exits non-zero with `SC2187` — and that diagnostic is a request rather than a refusal: it asks for `# shellcheck shell=dash` at the top of the file, and with the directive present the same file exits clean. Excluding ash therefore made its own documented remedy unreachable, because discovery dropped the file before `shellcheck` could read the directive it was asking for. Include it, and let the directive decide whether the job passes.

The second grep is what keeps that measurement honest. The optional `env` prefix in the first pattern applies to every alternative, so with `busybox sh` in the accepted set it would also admit `#!/usr/bin/env busybox sh` — the one spelling measured to raise `SC1008` — and the generated job would fail on a file this classifier was written to exclude. Rejecting the `env`-fronted form explicitly is cheaper than splitting the alternation into two shapes.

`busybox sh` is accepted too, and only by the spellings that name the binary directly — `#!/bin/busybox sh` and `#!/usr/bin/busybox sh` pass, while routing it through `env` raises `SC1008`. It is two tokens rather than one, which is why the alternation carries a whitespace class rather than a plain name.

Report the shells left out — `mksh` and `zsh`, both refused outright — by name as outside the generated job's reach. Dropping them silently, or feeding them to a tool that will refuse them, are the two failures this list exists between.

The pattern is anchored to the **interpreter's own position** rather than searching the line. A leading `.*` looks harmless and is not: it lets the match slide past the real interpreter to any later word, so `#!/usr/bin/env -S python -m bash` and `#!/usr/bin/python3 -c import bash` both read as shell and the generated job hands a Python file to a shell linter, which then fails for a reason that has nothing to do with the repository's shell. The path, the optional `env`, and the interpreter are matched in sequence instead.

The `env` segment carries an option run because `env` is not always a bare prefix. `#!/usr/bin/env -S bash -e` passes a flag through `env`, and a script may clear or set a variable before the interpreter — `env -S -i bash`, `env -S FOO=bar bash`. The pattern skips those first: any leading token that is a flag or a `NAME=value` assignment is stepped over before it looks for the interpreter, so a classifier that only took the interpreter directly after `env` no longer drops every script written that way. What it does not skip is an `env` option that consumes the _next_ token as its argument — `env -S -u DEBUG bash` unsets `DEBUG` and then runs `bash` — because skipping an arbitrary following word is exactly the slide-past the anchoring above forbids: the same latitude would read `#!/usr/bin/env -S python -m bash` as shell. That form is rare, and it is the one this classifier hands to the capability's interpreter-resolution rule rather than resolve here — reported as an unestablished shebang for the maintainer to place, not silently dropped as shell it could not confirm.

The extension branch runs the **same** accepted-set filter as the shebang branch, which is the point of taking the dialects as an argument at all. An earlier shape emitted every known extension unconditionally, so the two per-tool lists changed nothing for files without a shebang: a `.bats` file went to a formatter whose pinned version might not accept `bats`, and the generated job failed on a file the caller had deliberately excluded. Mapping each extension to the dialect it implies puts both branches under one rule.

`.husky/` is in that fallback for a reason the extension list cannot express: husky supplies the interpreter, its hooks are ordinarily written without a shebang, and a file called `pre-commit` has no extension either — so a classifier reading only shebangs and extensions drops the whole directory, which is the inventory promise this capability makes broken by the script meant to keep it. The manager runs them with `sh`, so `sh` is what they are classified as, and they face the accepted-set filter like everything else. `.husky/_/` is excluded because it is husky's own generated wrapper rather than the repository's code.

`.githooks/` is deliberately not given the same treatment, and the difference is evidence rather than tidiness. Nothing in the repository says what interprets a shebang-less file there — that is git's business and varies by platform — so classifying it would be the guess this capability's own routing rule forbids. Report such a file in the inventory as a script whose interpreter is unestablished, with adding a shebang as the prescription: one line makes it self-describing, at which point the shebang branch collects it like any other.

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
        run: <discovery> '<shellcheck dialects>' | xargs -0 --no-run-if-empty shellcheck --severity=warning --
      - name: shfmt
        run: <discovery> '<shfmt dialects>' | xargs -0 --no-run-if-empty shfmt -d --
```

Both downloads are checksum-verified before anything is extracted or made executable, and the digests are recorded here rather than fetched alongside the artifact. A version tag is not an identity: a release asset can be replaced without its URL changing, so a pinned version alone leaves the job executing whatever is behind that link today. The version pins which release the job wants; the digest is what makes the job refuse a different one. Fetching the checksums from the same host at the same time would verify only that the download was not corrupted in transit, which is not the question.

The binaries land in a runner-writable directory and reach the later steps through `GITHUB_PATH`, rather than being written straight into a system path. A job runs as an unprivileged user, so a scaffold that assumes it can write to `/usr/local/bin` risks failing before either check runs — and failing in the install step, where the error says nothing about shell linting.

`shfmt` is the reason this job needs an install step at all. `shellcheck` is preinstalled on the common hosted Ubuntu images and `shfmt` is not, so a job that assumes both fails on a fresh runner with `shfmt: command not found` — a scaffold that cannot run is worse than the gap it closes. A pinned setup action for either tool works equally well; the point is that both arrive deliberately.

Pinning both versions here is what keeps the scaffold consistent with what the router promises and with the scaffold contract that an addressed row re-audits clean. Taking `shellcheck` from the image is the cheaper-looking option and it is the one that produces a `floating` finding on the very next run — prescribing a shape the audit then reports is the contradiction this skill has now made seven times, and there is no reason to make it an eighth when the install step already exists for `shfmt`. The seventh is worth knowing about while reading this one: the rust toolchain template offered `stable` as a channel, which was fine until the day this skill started grading a floating channel as a finding, and nothing swept the templates when the grade moved.

`--severity=warning` is the gate the floor asks for, and leaving it off is not the neutral choice it looks like: `shellcheck` defaults to reporting every tier, so a job without the flag fails on `info` and `style` findings too — legacy backticks, a redundant `echo` — and hands a repository adopting this scaffold a stricter bar than the floor states on the day it lands. The tiers exist because their authors sorted them, and the rulebook these floors are shared with draws the line in the same place: errors and warnings gate a pipeline, and the two tiers below are the author's call. A wall of style findings on the first run is also how a team arrives at `continue-on-error`, which costs them the check the scaffold was written to give them.

The audit grades the floor's own line — errors and warnings both reaching the job — and leaves the tiers above it to the repository. Reporting `info` and `style` too is a stricter bar than the floor asks and no finding; raising the threshold the other way, to `--severity=error`, drops the warning tier the floor requires and is a finding, on an axis separate from whether the exit status is swallowed. A job can fail loudly on every error it emits and still sit below the floor for the warnings it never surfaces, so the audit reads the severity and the exit status as the two independent things they are. What the scaffold and the audit share is only the split of concern above: a scaffold hands over the house shape, and a report on somebody else's repository grades the substance against the floor.

`shfmt -d` prints a diff and exits non-zero when a file would change, which is the check-mode behavior; `shfmt -w` writes, and belongs nowhere near CI.

Hooks are the case worth being explicit about. If the inventory found `.githooks/` or `.husky/`, they are in the list, because an unlinted script is worth linting whether or not it currently runs. Their blast radius is conditional rather than given: a hook directory activated by `core.hooksPath` or an installer runs on every commit on every machine that ran the setup, and one nobody has wired runs nowhere. Say which of those the repository looks like rather than assuming the first — presenting an inert directory as active execution is the same conflation the audit is built to avoid.
