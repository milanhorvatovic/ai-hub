# Bash — concurrency

Bash concurrency is coarse-grained: background jobs and parallel process spawning. There are no threads; "concurrency" means running multiple processes.

> **The tools named below were last checked 2026-08.** The mechanics do not decay; the tools do. How to read a stamped file is stated once under "Currency" in `../../../SKILL.md`.

## Background jobs

```bash
long_task_a &
pid_a=$!
long_task_b &
pid_b=$!
wait "$pid_a" "$pid_b"      # block until both finish
```

- `&` backgrounds; `$!` captures the PID; `wait` joins.
- `wait` with no args waits for all children; `wait -n` (bash 4.3+) returns when *any* one finishes.
- Capture exit codes: `wait "$pid"; rc=$?` — a backgrounded job's failure is invisible without an explicit `wait`.

## Bounded parallelism

```bash
# process files N-at-a-time, bounded to CPU count
# getconf _NPROCESSORS_ONLN is portable (Linux/macOS/BSD); GNU `nproc` is Linux-only
printf '%s\0' *.txt | xargs -0 -P "$(getconf _NPROCESSORS_ONLN)" -n 1 process_one
```

- `xargs -P` is the simplest bounded-parallel primitive. `-0` / `printf '%s\0'` handles filenames with spaces.
- GNU `parallel` is more powerful (job logs, retries, `--halt` policies) when available.
- Don't spawn unbounded background jobs in a loop — `for f in *; do task "$f" & done` over 10,000 files forks a process bomb.

## Correctness traps

- **Subshells don't share state.** A `while read ... | ...` loop runs the loop body in a subshell — variable changes inside are lost. Use process substitution `done < <(cmd)` to keep the loop in the parent shell.
- **Interleaved output.** Parallel writes to the same file or to stdout interleave and corrupt. Write to per-job temp files and concatenate, or use `parallel`'s output grouping.
- **Race on shared files.** Two jobs appending to the same log race. Use `flock` (see `best-practices.md`) or per-job files.
- **`set -e` and background jobs** — `-e` does not trigger on a backgrounded job's failure; you must `wait` and check `$?`.

## When concurrency means "rewrite"

If you need shared mutable state, fine-grained coordination, or anything beyond fan-out-and-join, bash is the wrong tool. Move to a language with real concurrency primitives (see `best-practices.md` "when to leave bash").
