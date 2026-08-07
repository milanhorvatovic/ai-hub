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
  local workspace="$1" confirmed="${2:-0}" resolved
  # resolve before judging: `cd --` disarms a leading dash, `pwd -P` collapses
  # `..`, `//` and symlinks, so the check sees the path rm would actually act on
  resolved=$(cd -- "$workspace" 2>/dev/null && pwd -P) || return 0   # nothing there
  [[ "$resolved" != "/" ]] || {
    printf 'refusing to purge %q: resolves to /\n' "$workspace" >&2
    return 64                                   # EX_USAGE
  }

  if [[ "$confirmed" != 1 ]]; then
    printf 'would remove %s paths under %s\n' \
      "$(find "$resolved" -mindepth 1 | wc -l)" "$resolved" >&2
    return 0
  fi
  rm -rf -- "$resolved"
}
```

`rm -rf` cannot be undone, so caution is spent up front: the path is checked before it is interpolated, `--` stops a leading dash being read as a flag, and deleting takes an explicit second argument that a caller has to mean. A script that is safe only when its environment is set correctly is not safe.

Resolving before judging is doing more work than it looks like, and it is why the guard sits above both branches rather than beside `rm`. The reporting branch has no `--` to reach for: `find "$workspace" -mindepth 1` with a workspace of `-delete` becomes `find -delete -mindepth 1`, which finds no path operand, defaults its starting point to `.`, and deletes the tree you are standing in — from the branch whose entire job was to _not_ delete anything. `!` and `(` open a `find` expression the same way.

Which is the argument for checking the resolved value rather than the spelling. A blocklist of `-*` fixes the case you thought of and leaves the two you did not. Even demanding a leading `/` only looks safe: `//`, `/./` and `/var/tmp/../..` all satisfy it and all resolve to root. Ask the filesystem what the path _is_ — `cd --` disarms the leading dash, `pwd -P` collapses the traversals and symlinks — then judge that, and hand the resolved value to every command downstream. A check on how an argument is written is a check on the wrong thing; the commands act on where it points.

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
