# Architecture

Hexagonal-lite layout: pure domain modules, ports for I/O, thin entry shims. Loaded on demand when extending or debugging the skill — not needed to USE it.

## Layout

```text
scripts/
├── probe.py              entry shim — delegates to docs_steward.cli main
├── recommend-tools.py    entry shim — delegates to docs_steward.cli main
├── md-audit.py           entry shim — delegates to docs_steward.cli main
├── md-format.py          entry shim — delegates to docs_steward.cli main
├── md-audit-frontmatter.py  entry shim — delegates to docs_steward.cli main
├── docs_steward/
│   ├── __init__.py       public API exports (Event, EventType, Mode, Tool)
│   ├── __main__.py       enables `python -m docs_steward <subcommand>`
│   ├── cli.py            argparse + dispatch + NDJSON emission
│   ├── events.py         Event dataclass, EventType enum (single source of NDJSON vocab)
│   ├── tools.py          Tool enum, CommandTemplate, REGISTRY (single source of formatter catalog)
│   ├── modes.py          Mode enum (AUDIT, FORMAT)
│   ├── priority.py       INSTALL_PRIORITY (6-tool install-recommendation order)
│   ├── hints.py          install_hints(tool) — per-tool install commands across platforms
│   ├── baseline.py       BASELINE_CANDIDATES + detect_baseline(fs, root, override)
│   ├── selector.py       select_tool(baseline, runner) — preference + fallback semantics
│   ├── commands.py       build_command(tool, mode, unwrap, config_path) — registry-driven argv
│   ├── bundled_config.py bundled_config_for(tool) — path to shipped fallback config
│   ├── probe.py          probe_tools(runner) — inventory + exit-code contract
│   ├── recommend.py      recommend_installs(runner) — inventory + recommend + verdict
│   ├── runner.py         run_tool(mode, baseline, unwrap, runner, root) — orchestrator
│   ├── frontmatter.py    extract_blocks(text) — YAML frontmatter + fenced YAML extractor (pure)
│   ├── discovery.py      list_markdown_files(runner, root) — git ls-files + os.walk fallback
│   ├── yaml_audit.py     audit_frontmatter(runner, fs, files, config_path) — yamllint orchestrator
│   ├── emit.py           serialize(event) — JSON serialization (pure)
│   ├── process.py        ProcessRunner Protocol + SubprocessRunner adapter (subprocess seam)
│   ├── fs.py             FileSystem Protocol + OsFileSystem adapter (filesystem seam)
│   └── repo.py           repo_root(runner) — git rev-parse with cwd fallback
└── tests/
    ├── __init__.py
    ├── fakes.py          FakeProcessRunner + FakeFileSystem (the only test doubles needed)
    └── test_*.py         one module per source module; 100+ tests, sub-20ms wall time

assets/
└── configs/              bundled fallback configs used only when the repo declares none
    ├── README.md         scope, rationale, override paths
    ├── markdownlint.json applied via --config when running markdownlint / markdownlint-cli2
    ├── prettierrc.json   applied via --config when running prettier
    └── yamllint.yaml     applied via -c when running yamllint (md-audit-frontmatter)
```

## Port + adapter rationale

The `ProcessRunner` and `FileSystem` Protocols are the only seams between the package and the host environment. Every service function (`probe_tools`, `recommend_installs`, `run_tool`, `audit_frontmatter`, `repo_root`, `detect_baseline`) takes a port instance as a parameter — production code wires `SubprocessRunner` / `OsFileSystem`, tests inject `FakeProcessRunner` / `FakeFileSystem` from `tests/fakes.py`. No global state, no module-level subprocess calls, no implicit `os.getcwd()` inside business logic. Coverage stays at ≥95% on the orchestration codebase because every branch is reachable through fake-only setup; the uncovered lines are the real-I/O adapter bodies themselves (intentional — adapter-level tests would require a real subprocess and lose the speed guarantee).

## Adding a new formatter

Single source of truth: `docs_steward/tools.py`.

1. Add a new `Tool` enum member.
2. Add a `CommandTemplate` entry to `REGISTRY` with `audit` / `fmt` argv tuples and optional `config_flag` + `unwrap_flag`.
3. Add a `selector.py` `_BASELINE_PREFERENCES` entry mapping the tool's config-filename prefix to the tool.
4. Add a `hints.py` `_HINTS` entry with platform-specific install commands.
5. Decide whether the tool warrants priority — if yes, add to `priority.INSTALL_PRIORITY`.
6. Decide whether a bundled fallback config is shippable — if yes, drop the file under `assets/configs/` and wire it into `bundled_config.py`.
7. Add tests in `tests/test_commands.py` (per-mode argv) and `tests/test_selector.py` (baseline-preference resolution).

No changes to `runner.py`, `cli.py`, or any entry shim — the architecture absorbs new formatters by registry extension.

## Adding a new file-type pipeline

When a non-markdown surface lands (e.g. RST, AsciiDoc), the pattern is:

1. New pure-Python parser module (e.g. `rst_blocks.py`) following `frontmatter.py`'s shape.
2. New service module (e.g. `rst_audit.py`) following `yaml_audit.py`'s shape — takes ports as parameters, returns `(events, exit_code)`.
3. New CLI subcommand in `cli.py` + dispatcher entry.
4. New entry shim under `scripts/` (e.g. `rst-audit.py`).
5. Tests under `tests/` (parser + service).

No existing module needs modification; the addition is purely additive.
