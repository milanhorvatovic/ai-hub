# Bash — examples by principle

Concrete before/after code anchored to numbered principles from the parent skill. The principle prose lives in `../../../references/principles.md`; the language idioms and rules live in `../capability.md`. This file holds only the code.

## Principle 2 — Root cause over bandaid (failing-first)

```bash
# bandaid — silences the failing command instead of understanding it
deploy.sh || true              # exit code lost; pipeline reports green
make build 2>/dev/null         # error message thrown away
```

```bash
# root-cause — let it fail loudly; if a fallback is intentional, name it
if ! deploy.sh; then
  echo "deploy failed; rolling back" >&2
  rollback.sh
  exit 1
fi
```

## Principle 5 — Trust internal code; validate at boundaries

```bash
# defensive — re-checks values internal code already produced
process_file() {
  local path="$1"
  if [[ -z "$path" ]]; then return 1; fi
  if [[ ! -f "$path" ]]; then return 1; fi
  if [[ ! -r "$path" ]]; then return 1; fi
  # caller already passed a valid, readable path; these checks belong at the entry point
  cat "$path"
}
```

```bash
# trust the contract; validate once at the entry
main() {
  local path="${1:?usage: main <path>}"
  [[ -f "$path" && -r "$path" ]] || { echo "not a readable file: $path" >&2; exit 2; }
  process_file "$path"
}

process_file() {
  cat "$1"     # internal — trust the caller
}
```

## Principle 11 — Reversibility shapes caution

```bash
# unset or empty $WORKSPACE makes this `rm -rf /`, and nothing shows the
# operator what is about to go before it is gone
rm -rf "$WORKSPACE/"
```

```bash
# the destructive path is the one you have to ask for; the default reports
purge_workspace() {
  local name="$1" confirmed="${2:-0}" root="${WORKSPACE_ROOT:?WORKSPACE_ROOT is required}" dir
  # the caller names a workspace and never supplies a path, so traversal, a
  # leading dash and a trailing slash are unrepresentable rather than screened
  [[ "$name" =~ ^[A-Za-z0-9_-]+$ ]] || {
    printf 'refusing to purge %q: names are [A-Za-z0-9_-]+\n' "$name" >&2
    return 64                                   # EX_USAGE
  }
  [[ "$root" = /* ]] || {
    printf 'WORKSPACE_ROOT must be absolute, got %q\n' "$root" >&2
    return 78                                   # EX_CONFIG
  }

  dir="$root/$name"                             # built, so it has no odd spelling
  [[ ! -L "$dir" ]] || {
    printf 'refusing to purge %q: %s is a symlink\n' "$name" "$dir" >&2
    return 64
  }
  [[ -d "$dir" ]] || return 0                   # nothing to purge

  if [[ "$confirmed" != 1 ]]; then
    printf 'would remove %s paths under %s\n' "$(find "$dir" -mindepth 1 | wc -l)" "$dir" >&2
    return 0
  fi
  rm -rf -- "$dir"
}
```

`rm -rf` cannot be undone, so caution is spent up front: the path is checked before it is interpolated, `--` stops a leading dash being read as a flag, and deleting takes an explicit second argument that a caller has to mean. A script that is safe only when its environment is set correctly is not safe.

The interesting part is what the rewrite refused to do, because the obvious fix does not converge. Accept a path and you owe it a validator, and every check you write teaches you the next spelling: `-delete` makes `find "$workspace" -mindepth 1` into `find -delete -mindepth 1`, which takes no path operand, defaults to `.`, and deletes the tree you are standing in — from the branch whose only job was to _not_ delete anything. Reject a leading dash and `!` and `(` open a `find` expression the same way. Demand a leading `/` and `//`, `/./` and `/var/tmp/../..` all satisfy it and all resolve to root. Resolve with `pwd -P` and a workspace whose last component is a symlink now resolves to its target, so the safe-looking version deletes what the link points at where plain `rm` would have unlinked it — destroying strictly more than the naive code it replaced. Guard that with `-L` and a trailing slash slips past, because `[[ -L link/ ]]` is false while `cd link/ && pwd -P` still lands on the target.

That is five rounds of validator against an input that has more spellings than you have checks, and the lesson is not the fifth check. Take a name instead of a path. `[A-Za-z0-9_-]+` cannot express a traversal, a leading dash, a trailing slash, or a second path component, so none of those need screening — they stopped being sayable. Build the path yourself from a root you validated once at the edge, and the only hazard left is the one the construction cannot rule out, a symlink sitting where you put the directory, which is a single reliable check because the path you are testing has no odd spelling in it.

Reversibility is what makes the trade worth it. A validator that is wrong about a search argument returns bad results; a validator that is wrong here removes a filesystem. When the operation cannot be undone, narrow what it can be _asked_ to do until the dangerous inputs are unrepresentable — an argument you cannot express is one you never have to get right.

## Principle 13 — Security hygiene (no secrets in process listing or logs)

```bash
# leaks the secret to anyone running `ps`; also into shell history
curl -H "Authorization: Bearer $API_TOKEN" "$URL"   # token visible in `ps aux`
mysql -u root -p"$DB_PASSWORD" -e "..."             # password visible in `ps aux`
echo "deploying with token=$API_TOKEN" >> deploy.log
```

```bash
# pass secrets via env or files, not argv; never log them
mysql --defaults-extra-file=<(printf '[client]\npassword=%s\n' "$DB_PASSWORD") -e "..."
echo "deploying" >> deploy.log                       # log shape, not values
```

## Principle 16 — Inject time, randomness, and external state

```bash
# reads the clock and the environment from inside the logic
build_report() {
  local out="/var/reports/report-$(date +%F).csv"
  psql "service=$PG_SERVICE" -c "select ..." >"$out"
}
```

```bash
# date, destination, and connection arrive as arguments; main() reads the
# environment once, at the edge, and fails loudly when it is not set
build_report() {
  local report_date="$1" out_dir="$2" pg_service="$3"
  # a service name, not a URL: credentials stay in ~/.pg_service.conf and
  # .pgpass, so nothing secret reaches argv or `ps aux` (principle 13)
  psql "service=$pg_service" -c "select ..." >"$out_dir/report-$report_date.csv"
}

main() {
  build_report \
    "$(date +%F)" \
    "${REPORT_DIR:?REPORT_DIR is required}" \
    "${PG_SERVICE:?PG_SERVICE is required}"
}

# the test calls the function directly — fixed date, temp dir, no clock, no env
build_report 2026-01-01 "$BATS_TEST_TMPDIR" reports_test
```

## Principle 19 — Boundaries parse input

```bash
# trusts argv positions; silent failure when positions shift
target_dir="$1"
flag="$2"
files="$3"
```

```bash
# parse explicitly with getopts; reject malformed input at the entry
usage() { echo "usage: $0 [-f] -t <dir> <files...>"; exit 2; }
force=0
target=
while getopts ":ft:" opt; do
  case "$opt" in
    f) force=1 ;;
    t) target="$OPTARG" ;;
    \?) usage ;;
  esac
done
shift $((OPTIND - 1))
[[ -n "$target" ]] || usage
[[ $# -ge 1 ]] || usage
# downstream code receives validated values
```

## Principle 21 — Comments earn their place

```bash
# section markers that restate the structure, and a bare disable
# ---- setup ----
set -euo pipefail

# shellcheck disable=SC1091
source "$script_dir/lib/common.sh"

# ---- main ----
main "$@"
```

```bash
set -euo pipefail

# Resolved from $script_dir at runtime, so shellcheck cannot follow it to check.
# shellcheck disable=SC1091
source "$script_dir/lib/common.sh"

main "$@"
```

The markers were describing what the reader can already see; the disable was the one place a reader could not tell whether the linter had been silenced for a reason or for convenience. Note which disable earned its comment: one shellcheck genuinely cannot resolve. A disable that exists because the code took the wrong shape — `SC2086` on an unquoted list, say — is a design note in disguise, and the honest fix is the array this capability already asks for, not a justification for keeping the string. A script's header block is the standing exception in this language — an interface with nowhere else to live, covered in `best-practices.md` — not a licence for the rest of the file.
