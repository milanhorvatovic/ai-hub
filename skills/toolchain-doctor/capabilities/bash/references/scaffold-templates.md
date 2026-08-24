# bash — scaffold templates

Shapes to fill in from what the scan found. Placeholders in angle brackets are values the scan already established — and for this language the most important of them is the file list, which comes from the inventory rather than from a glob.

## `.shellcheckrc`

```ini
# Dialect for files whose shebang does not declare one.
shell=bash

# Follow sourced files rather than warning about them; source paths are
# relative to the invocation, so keep CI and local invocations in one place.
external-sources=true
```

Do not scaffold a `disable=` line here. A repository-wide suppression turns off a check for every script including the ones written next year, and the floor's position is that a suppression carries a one-line reason at the site it applies to. Where an audit found a rule that genuinely does not fit the repository, propose the per-file directive with its reason instead:

```bash
# shellcheck disable=SC2086  # word splitting is intended: $FLAGS carries multiple args
run_tool $FLAGS
```

## `shfmt` settings in `.editorconfig`

`shfmt` reads `.editorconfig`, which is also what a contributor's editor reads — one declaration for both, instead of flags that live only in a CI step.

```ini
[*.sh]
indent_style = space
indent_size = 2
switch_case_indent = true
binary_next_line = true
```

`switch_case_indent` and `binary_next_line` are the `-ci` and `-bn` flags spelled as settings. When the repository already invokes `shfmt` with flags somewhere, translate the flags it uses rather than imposing these — a reformat of every script is a large diff to hand someone who asked for a config file.

## Finding the files to check

The list comes from the inventory, not a glob. This is the shape that reaches the scripts a `*.sh` pattern misses:

```bash
#!/usr/bin/env bash
set -euo pipefail

# Tracked files that are shell: by extension, or by shebang.
mapfile -t files < <(
  {
    git ls-files -z '*.sh' '*.bash' | tr '\0' '\n'
    git grep -lIz --untracked -e '' -- . 2>/dev/null | tr '\0' '\n' |
      while IFS= read -r f; do
        [ -f "$f" ] || continue
        head -n 1 -- "$f" | grep -Eq '^#!.*\b(ba)?sh\b' && printf '%s\n' "$f"
      done
  } | sort -u
)

printf '%s\n' "${files[@]}"
```

Run it once and read the output before wiring it into CI. The list is the audit's evidence, and a maintainer looking at it will spot both a missing script and a wrongly included one faster than any heuristic here can.

## The CI step

```yaml
shell:
  runs-on: ubuntu-latest
  steps:
    - uses: actions/checkout@<40-char-sha> # v5
    - name: shellcheck
      run: |
        shopt -s globstar
        shellcheck <the inventory's files, or the discovery command above>
    - name: shfmt
      run: shfmt -d <the same file list>
```

`shellcheck` is preinstalled on GitHub's Ubuntu runners, so this step needs no install — one of the few places where the floor costs nothing to adopt. `shfmt -d` prints a diff and exits non-zero when a file would change, which is the check-mode behavior; `shfmt -w` writes, and belongs nowhere near CI.

Hooks are the case worth being explicit about. If the inventory found `.githooks/` or `.husky/`, they are in the list — they run on every commit on every contributor's machine, which makes them the shell in the repository with the widest blast radius and, almost always, the least review.
