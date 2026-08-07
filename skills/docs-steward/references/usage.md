# Usage

Concrete commands the skill ships. SKILL.md describes what each does conceptually; this file owns the CLI I/O contract: the cheatsheet, discovery, and the stdout / exit-code semantics.

## Entry shims

```sh
scripts/probe.py                                          # list available formatters + versions (+ mdformat plugins)
scripts/recommend-tools.py                                # prioritized install recommendations for what is missing
scripts/md-audit.py                                       # read-only check; auto-detect baseline + tool
scripts/md-audit.py --unwrap                              # also pass --prose-wrap=never / --wrap=no
scripts/md-audit.py --baseline .prettierrc                # force the formatter owner's baseline (complementary passes stay repo-derived)
scripts/md-audit.py --quiet                               # drop formatter preamble (banner / summary lines)
scripts/md-audit.py docs/intro.md README.md               # scope to explicit files (per-file targeting)
scripts/md-format.py [--unwrap] [--baseline FILE] [--quiet] [FILE...]  # write mode (modifies files)
scripts/md-format.py --dry-run                            # preview changes without writing (emits would-change events)
scripts/md-fix.py [--unwrap] [--baseline FILE] [--quiet] [FILE...]     # one-shot: audit → format → re-audit → delta
scripts/md-audit-frontmatter.py [FILE...]                 # lint YAML frontmatter + fenced YAML blocks (yamllint)
scripts/md-audit-frontmatter.py --yamllint-config .yamllint  # force a specific yamllint config (overrides auto-discovery)
```

**Discovery:** `discovery.list_markdown_files` returns absolute paths to every `.md` / `.markdown` file under the repo root, via `git ls-files --cached --others --exclude-standard` (covers tracked and untracked-but-not-ignored files; respects `.gitignore`) or, when git is unavailable, an `os.walk` fallback — which does not read `.gitignore`; in that mode only the fixed skip list applies. Either path filters entries under `node_modules`, `.git`, `dist`, `build`, `.venv`, `venv`, `target` and drops paths whose working-tree file is missing or is a directory. Repo-root detection (`repo.repo_root`) uses `git rev-parse --show-toplevel`, falling back to the current working directory when git is absent. Per-tool ignore files (`.prettierignore`, `.markdownlintignore`) still apply within each tool's own pass.

**Per-file targeting:** any audit/format/fix entry accepts positional file paths as the last arguments. When provided, they replace the discovered inventory for every pass of the run; when omitted, `discovery.list_markdown_files` supplies the shared inventory and each tool is invoked on that explicit list rather than its own default glob. Works without git — explicit files are passed through as given.

**Composite audit:** `md-audit` (and `md-fix` after its cycle) runs every applicable pass — the formatter owner, the complementary markdownlint lint pass, and (when `yamllint` is on PATH) the frontmatter pass — each with its own `selected` event and its own family's config, aggregated into one exit code via maximum. An empty inventory short-circuits with a single `clean` event and exit 0.

**`--quiet`:** suppresses formatter preamble lines (banners like `Linting: 3 file(s)` / `Summary: 0 error(s)`). Real `finding` / `changed` / `error` events still flow.

**`--dry-run`** (md-format only): runs the formatter's check invocation, emits `would-change` events for files that would be modified. No writes performed.

**`md-fix.py`:** audit → format → re-audit → emit `delta` event with `{resolved, still_open, new}` counts. Bails early if pre-audit hits an error.

All emitted events go to stdout as NDJSON via `cli._emit`. The CLI does not write its own progress or error messages to stderr — invocation errors (unknown subcommand, missing required argument) surface via argparse's stderr usage messages, but routine progress is encoded inside the event stream itself (`selected`, `bundled-config`, `clean`, `missing`, `error` events) rather than as a separate stderr channel. Formatter subprocess output is captured and routed through the event stream too; no formatter bytes reach the terminal directly.

Exit codes (uniform across the entry shims): `0` clean / `1` findings (or files changed) / `2` invocation error / `3` no usable tool. Exception: `recommend-tools.py` exits `0` (top-priority tool present) or `1` (at least one priority tool missing) only.

## Python-module invocation

```sh template
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
