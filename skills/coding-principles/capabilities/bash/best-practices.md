# Bash — industry best practices

External standards, modern toolchain consensus, security and operational conventions that complement the principle-anchored content in `capability.md`. Cite these references when the agent's choices need justification beyond the parent skill's principles.

## External standards

- **[Google Shell Style Guide](https://google.github.io/styleguide/shellguide.html)** — the de facto external standard. Covers indentation (2-space), function naming, `[[ ]]` over `[ ]`, when to use `local`, etc. Where this capability and Google's guide agree, follow both; where they differ, the parent skill's principles win (and we flag the divergence here).

## POSIX vs bash decision

Default to `#!/usr/bin/env bash` for any script over ~20 lines or that uses arrays / `[[ ]]` / `${var,,}` / process substitution. Drop to `#!/bin/sh` only when the script must run on POSIX-only environments — Alpine/`busybox`, init systems, container entrypoints on minimal base images — and limit yourself to POSIX features there.

Do not write "portable bash" that tip-toes around bashisms. Either commit to bash (and assume bash 4+) or commit to POSIX.

## Exit codes (sysexits.h convention)

Pick exit codes that callers can match on. The traditional `0` (success) / `1` (general error) is fine for small scripts; for anything that participates in a pipeline or is invoked by automation, follow `sysexits.h`:

| Code | Name              | Meaning                              |
| ---- | ----------------- | ------------------------------------ |
| 0    | EX_OK             | Success                              |
| 64   | EX_USAGE          | Command-line usage error             |
| 65   | EX_DATAERR        | Data format error                    |
| 66   | EX_NOINPUT        | Cannot open input                    |
| 69   | EX_UNAVAILABLE    | Service unavailable                  |
| 70   | EX_SOFTWARE       | Internal software error              |
| 75   | EX_TEMPFAIL       | Temporary failure (retry-safe)       |
| 77   | EX_NOPERM         | Permission denied                    |
| 78   | EX_CONFIG         | Config error                         |

Document non-zero codes the script uses in `--help` so callers know what to branch on.

## 12-factor CLI discipline

For scripts that compose with other tools:

- **stdout = data** (parseable; pipe-target).
- **stderr = narration** (progress, warnings, info messages).
- **env = configuration** (read at startup; do not hardcode paths or URLs).
- **argv = behavior** (flags and positional args that change *what* the script does).

Don't write progress messages to stdout if anything downstream might pipe the output. Don't expect interactive prompts unless the script is explicitly interactive — pipelines run with no TTY.

Respect [`NO_COLOR`](https://no-color.org/): if `NO_COLOR` is set and non-empty, do not emit ANSI color escapes. Check with `[[ -n "${NO_COLOR:-}" ]] && color="" || color=$'\033[0;31m'`.

## Single-instance locking

For scripts that must not run concurrently (cron jobs, deploys, migrations):

```bash
lockfile="/var/lock/$(basename "$0").lock"
exec {fd}>"$lockfile"
flock -n "$fd" || { echo "another instance is running" >&2; exit 75; }   # EX_TEMPFAIL
```

`flock -n` (non-blocking) is the right default for cron — a missed run is usually preferable to two parallel runs. Use blocking `flock` (`-w <seconds>`) only when serialization is the actual goal.

## Cleanup on exit

Always trap `EXIT` for tempfile cleanup; trap `INT TERM` to propagate signals cleanly:

```bash
tmp=$(mktemp -d)
cleanup() { rm -rf "$tmp"; }
trap cleanup EXIT
trap 'cleanup; trap - INT; kill -INT $$' INT
trap 'cleanup; trap - TERM; kill -TERM $$' TERM
```

The signal-replay pattern (clear the trap, re-raise) makes `Ctrl-C` exit with the conventional `130` status rather than `0`.

## ShellCheck severity discipline

ShellCheck warnings have severity classes (`error`, `warning`, `info`, `style`). CI should fail on `error` and `warning`; `info` and `style` are author choices.

`# shellcheck disable=SCnnnn` requires a one-line justification immediately above. Bare disables are unreviewable.

## Toolchain consensus (modern)

- **Linter**: `shellcheck` — non-negotiable. Run on every script.
- **Formatter**: `shfmt -i 2 -ci -bn -sr` is a sane default. Some teams prefer `-i 4`; match the repo.
- **Test runner**: `bats-core` for non-trivial scripts; `shunit2` if `bats` isn't available.
- **Debugger**: `bash -x script.sh` for one-off tracing; `PS4='+ ${BASH_SOURCE}:${LINENO}:${FUNCNAME[0]:-main}() '` to make `-x` output useful.

## When to leave bash

Past ~200 lines / multiple subcommands / structured I/O (JSON, YAML, anything that isn't lines-of-text), rewrite in Python or Go. The maintenance cost of bash grows non-linearly past that boundary.

## Security

- **Never** `eval` user input or values from untrusted sources. There is almost always a structured alternative.
- **Never** put secrets in argv — they show up in `ps aux` for anyone on the host. Use env vars, files (`--password-file=`), or stdin redirection (`--defaults-extra-file=<(...)`).
- **Always** quote variable expansions in commands that take a path or pattern; unquoted `rm -rf "$dir/"` becomes catastrophic when `$dir` is empty.
- **Use `set -u`** to catch unset-variable bugs that would otherwise expand to empty strings.

## Documentation

- **Usage / `--help`** — every script that takes arguments prints usage on `-h`/`--help` and on a usage error (exit 64). Keep the usage string adjacent to the argument parsing so they don't drift.
- **Header comment block** — a short block at the top: what the script does, required env vars, exit codes, an example invocation. Not a changelog (git holds that).
- **Function comments** — only where the *why* is non-obvious (parent skill principle 7). Bash has no docstring convention; a one-line comment above a non-trivial function is the norm.
