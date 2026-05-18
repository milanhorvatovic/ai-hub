# Usage

Concrete commands the skill ships. SKILL.md describes what each does conceptually; this file is the cheatsheet.

## Entry shims

```sh
scripts/probe.py                                          # list available formatters + versions (+ mdformat plugins)
scripts/recommend-tools.py                                # prioritized install recommendations for what is missing
scripts/md-audit.py                                       # read-only check; auto-detect baseline + tool
scripts/md-audit.py --unwrap                              # also pass --prose-wrap=never / --wrap=no
scripts/md-audit.py --baseline .prettierrc                # force baseline (skip detection)
scripts/md-audit.py --quiet                               # drop formatter preamble (banner / summary lines)
scripts/md-audit.py docs/intro.md README.md               # scope to explicit files (per-file targeting)
scripts/md-format.py [--unwrap] [--baseline FILE] [--quiet] [FILE...]  # write mode (modifies files)
scripts/md-format.py --dry-run                            # preview changes without writing (emits would-change events)
scripts/md-fix.py [--unwrap] [--baseline FILE] [--quiet] [FILE...]     # one-shot: audit → format → re-audit → delta
scripts/md-audit-frontmatter.py [FILE...]                 # lint YAML frontmatter + fenced YAML blocks (yamllint)
scripts/md-audit-frontmatter.py --yamllint-config .yamllint  # override the bundled yamllint config
```

**Per-file targeting:** any audit/format/fix entry accepts positional file paths as the last arguments. When provided, the formatter scopes to exactly those files (bypassing its default glob). Works without git — the file list is passed verbatim.

**`--quiet`:** suppresses formatter preamble lines (banners like `Linting: 3 file(s)` / `Summary: 0 error(s)`). Real `finding` / `changed` / `error` events still flow.

**`--dry-run`** (md-format only): runs the formatter's check invocation, emits `would-change` events for files that would be modified. No writes performed.

**`md-fix.py`:** audit → format → re-audit → emit `delta` event with `{resolved, still_open, new}` counts. Bails early if pre-audit hits an error.

NDJSON on stdout, progress + errors on stderr.

Exit codes (uniform across all entry shims): `0` clean / `1` findings (or files changed) / `2` invocation error / `3` no usable tool.

## Python-module invocation

```sh
python3 -m docs_steward <subcommand>   # from inside the scripts/ directory
```

Subcommands: `probe`, `recommend-tools`, `md-audit`, `md-format`, `md-fix`, `md-audit-frontmatter`. Same exit codes as the entry shims.

## Running tests

The test suite lives at the repo root under `tests/skills/docs_steward/` and is driven by `pytest` (pinned in `requirements-test.txt`). From the repo root:

```sh
pip install -r requirements-test.txt
pytest tests/skills/docs_steward/            # docs-steward suite only
pytest                                       # full repo suite

# optional coverage (requires the `coverage` package):
coverage run --source=skills/docs-steward/scripts/docs_steward -m pytest tests/skills/docs_steward/ && coverage report -m
```

`tests/skills/docs_steward/conftest.py` injects `skills/docs-steward/scripts/` onto `sys.path` so the suite imports `docs_steward` without packaging. CI runs the same `pytest` invocation across {ubuntu-latest, windows-latest} × {3.12, 3.13} — see `.github/workflows/tests.yml`.

Expected: 140+ tests pass in well under a second; coverage ≥95% on the orchestration codebase.
