# Bash — performance

Performance idioms for Bash. Apply *after* correctness and clarity (the parent skill's KISS + readability goals outrank micro-optimization); these matter most in scripts that loop over large inputs or run on a hot path.

## Avoid forking in loops

Every external command (`sed`, `awk`, `grep`, `cut`, `basename`) is a `fork+exec`. In a loop over thousands of lines, that dominates runtime.

```bash
# slow — forks `basename` once per file
for f in *.txt; do
  name=$(basename "$f" .txt)   # fork per iteration
done
```

```bash
# fast — parameter expansion, no fork
for f in *.txt; do
  name=${f##*/}; name=${name%.txt}
done
```

Prefer bash builtins and parameter expansion over external tools for per-iteration work.

## Read files efficiently

```bash
# slow — useless cat fork + per-line read overhead
while read -r line; do process "$line"; done < <(cat file)
```

```bash
# fast — mapfile reads the whole file into an array in one call
mapfile -t lines < file
for line in "${lines[@]}"; do process "$line"; done
```

For huge files that won't fit in memory, `while read -r line; do ...; done < file` (no `cat`) is correct — stream, don't slurp.

## Do work in one pass

- One `awk`/`sed` invocation that does five transforms beats five piped invocations.
- One `grep -E 'a|b|c'` beats three `grep` calls.
- Avoid `cat file | grep` (useless cat — see `anti-patterns.md`); `grep pattern file` reads directly.

## Parallelism for independent work

```bash
# process files in parallel, bounded to CPU count
printf '%s\0' *.txt | xargs -0 -P "$(nproc)" -n 1 process_one
```

`xargs -P` or GNU `parallel` for embarrassingly-parallel tasks. See `concurrency.md` for correctness caveats.

## Measure, don't guess

- `time ./script.sh` for wall-clock.
- `bash -x` with `PS4='+ $EPOCHREALTIME '` to find slow lines.
- For anything where performance genuinely matters and the logic is non-trivial, that's the signal to rewrite in a faster language (see `best-practices.md` "when to leave bash").

The parent skill's stance holds: don't optimize a script that runs once a day in 200ms. Optimize the cron job that processes a million lines.
