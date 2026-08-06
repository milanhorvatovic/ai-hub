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
  psql "$DATABASE_URL" -c "select ..." >"$out"
}
```

```bash
# date, destination, and connection arrive as arguments; main() reads the
# environment once, at the edge, and fails loudly when it is not set
build_report() {
  local report_date="$1" out_dir="$2" database_url="$3"
  psql "$database_url" -c "select ..." >"$out_dir/report-$report_date.csv"
}

main() {
  build_report \
    "$(date +%F)" \
    "${REPORT_DIR:?REPORT_DIR is required}" \
    "${DATABASE_URL:?DATABASE_URL is required}"
}

# the test calls the function directly — fixed date, temp dir, no clock, no env
build_report 2026-01-01 "$BATS_TEST_TMPDIR" "$TEST_DATABASE_URL"
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

# shellcheck disable=SC2086
run_job $args

# ---- main ----
main "$@"
```

```bash
set -euo pipefail

# shellcheck disable=SC2086 — $args is a pre-split flag list from build_args();
# quoting it would hand run_job every flag as a single argument.
run_job $args

main "$@"
```

The markers were describing what the reader can already see; the disable was the one place a reader could not tell whether the unquoted expansion was deliberate. A script's header block is the standing exception in this language — an interface with nowhere else to live, covered in `best-practices.md` — not a licence for the rest of the file.
