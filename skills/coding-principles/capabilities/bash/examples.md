# Bash — examples by principle

Concrete before/after code anchored to numbered principles from the parent skill. The principle prose lives in `../../references/principles.md`; the language idioms and rules live in `capability.md` (sibling). This file holds only the code.

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
