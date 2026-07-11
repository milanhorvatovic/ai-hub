"""Command-line entry point.

`main(argv)` parses subcommand + flags, wires the concrete adapters
(`SubprocessRunner`, `OsFileSystem`), calls the matching service, emits each
event as NDJSON on stdout, and returns the service's exit code. The function
takes `argv` as a parameter (not `sys.argv` implicitly) so tests can call
`main(["probe"])` directly without subprocess.

Subcommand → service map:
    probe                  -> probe.probe_tools
    recommend-tools        -> recommend.recommend_installs
    md-audit               -> runner.run_tool(mode=AUDIT, ...)
    md-format              -> runner.run_tool(mode=FORMAT, ...)
    md-fix                 -> runner.run_fix_cycle (audit → format → re-audit → delta)
    md-audit-frontmatter   -> yaml_audit.audit_frontmatter
"""

from __future__ import annotations

import argparse
import os
import sys
from collections.abc import Callable, Iterable, Sequence

from .baseline import UNIVERSAL_SUBSET, detect_baseline
from .discovery import list_markdown_files
from .emit import serialize
from .events import Event
from .fs import FileSystem, OsFileSystem
from .modes import Mode
from .paths import is_absolute, posix_join, to_posix
from .plugins import detect_installed_plugin_labels, emit_plugin_missing
from .probe import probe_tools
from .process import ProcessRunner, SubprocessRunner
from .recommend import recommend_installs
from .repo import repo_root
from .runner import run_fix_cycle, run_tool
from .selector import select_tool
from .tools import Tool
from .yaml_audit import audit_frontmatter


def _add_files_arg(cmd: argparse.ArgumentParser) -> None:
    cmd.add_argument(
        "files",
        nargs="*",
        help=(
            "Optional explicit file paths to scope the run to. When omitted, "
            "the formatter runs against its default glob over the repo root."
        ),
    )


def _add_quiet_arg(cmd: argparse.ArgumentParser) -> None:
    cmd.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress formatter preamble (banner / summary lines).",
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="docs-steward",
        description="Markdown formatter orchestrator with NDJSON output.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("probe", help="List available formatters on PATH.")
    sub.add_parser(
        "recommend-tools",
        help="Inventory installed formatters and recommend missing ones by priority.",
    )

    # md-audit + md-format share unwrap/baseline/files/quiet; md-format adds dry-run.
    for name, mode_help in (
        ("md-audit", "Run the chosen markdown formatter in read-only check mode."),
        ("md-format", "Run the chosen markdown formatter in write mode (modifies files)."),
    ):
        cmd = sub.add_parser(name, help=mode_help)
        cmd.add_argument(
            "--unwrap",
            action="store_true",
            help="Pass the formatter's 'no prose wrap' flag.",
        )
        cmd.add_argument(
            "--baseline",
            type=str,
            default=None,
            help="Force a style baseline (skip auto-detection).",
        )
        _add_quiet_arg(cmd)
        if name == "md-format":
            cmd.add_argument(
                "--dry-run",
                action="store_true",
                help=(
                    "Show what would change without writing. Emits `would-change` "
                    "events; runs the formatter's check invocation under the hood."
                ),
            )
        _add_files_arg(cmd)

    fix_cmd = sub.add_parser(
        "md-fix",
        help="One-shot loopback: audit → format → re-audit → emit delta event.",
    )
    fix_cmd.add_argument(
        "--unwrap",
        action="store_true",
        help="Pass the formatter's 'no prose wrap' flag.",
    )
    fix_cmd.add_argument(
        "--baseline",
        type=str,
        default=None,
        help="Force a style baseline (skip auto-detection).",
    )
    _add_quiet_arg(fix_cmd)
    _add_files_arg(fix_cmd)

    frontmatter_cmd = sub.add_parser(
        "md-audit-frontmatter",
        help="Lint YAML frontmatter + fenced YAML blocks in markdown files via yamllint.",
    )
    frontmatter_cmd.add_argument(
        "--yamllint-config",
        type=str,
        default=None,
        help=(
            "Path to a yamllint config; overrides auto-discovery and the "
            "bundled fallback. When omitted, the CLI probes the repo root "
            "for .yamllint / .yamllint.yaml / .yamllint.yml (yamllint's own "
            "standalone lookup order); only when none of those exists does "
            "the bundled assets/configs/yamllint.yaml apply."
        ),
    )
    _add_files_arg(frontmatter_cmd)

    return parser


def _emit(events: Iterable[Event]) -> None:
    """Print each event as NDJSON. Uses sys.stdout dynamically so tests can
    redirect via `patch('sys.stdout', buf)` without binding at import time."""
    for event in events:
        print(serialize(event))


def _dispatch_probe(_: argparse.Namespace, runner: ProcessRunner) -> tuple[list[Event], int]:
    return probe_tools(runner)


def _dispatch_recommend(_: argparse.Namespace, runner: ProcessRunner) -> tuple[list[Event], int]:
    return recommend_installs(runner)


def _dispatch_audit(args: argparse.Namespace, runner: ProcessRunner) -> tuple[list[Event], int]:
    return _dispatch_run(args, runner, Mode.AUDIT, dry_run=False)


def _dispatch_format(args: argparse.Namespace, runner: ProcessRunner) -> tuple[list[Event], int]:
    return _dispatch_run(args, runner, Mode.FORMAT, dry_run=getattr(args, "dry_run", False))


def _dispatch_run(
    args: argparse.Namespace, runner: ProcessRunner, mode: Mode, dry_run: bool = False,
) -> tuple[list[Event], int]:
    fs = OsFileSystem()
    root = repo_root(runner)
    baseline = detect_baseline(fs, root, args.baseline)
    files = _files_or_none(args)
    plugin_events = _maybe_plugin_missing_events(runner, fs, baseline, files, root)
    events, code = run_tool(
        mode=mode,
        baseline=baseline,
        unwrap=args.unwrap,
        runner=runner,
        root=root,
        files=files,
        quiet=getattr(args, "quiet", False),
        dry_run=dry_run,
    )
    lint_events, lint_code = _markdownlint_lint_pass(
        args, runner, root, baseline, files, mode
    )
    return plugin_events + events + lint_events, max(code, lint_code)


_MARKDOWNLINT_TOOLS: tuple[Tool, ...] = (Tool.MARKDOWNLINT_CLI2, Tool.MARKDOWNLINT)


def _markdownlint_lint_pass(
    args: argparse.Namespace,
    runner: ProcessRunner,
    root: str,
    baseline: str,
    files: Sequence[str] | None,
    mode: Mode,
) -> tuple[list[Event], int]:
    """Complementary markdownlint lint pass, run alongside the formatter.

    In AUDIT mode, when the chosen formatter is not markdownlint and a
    markdownlint binary is on PATH, run markdownlint lint-only (bundled
    config) so the semantic `MD###` rules are reported even though prettier
    (or another formatter) owns formatting — prettier handles wrap/tables/
    whitespace, markdownlint flags MD040 / MD036 / MD033 / MD034 / … that
    prettier ignores. Returns `([], 0)` (no-op) outside audit, when no
    markdownlint binary is available, or when the formatter already IS
    markdownlint (its own pass covers the rules).
    """
    if mode != Mode.AUDIT:
        return [], 0
    if select_tool(baseline, runner) in _MARKDOWNLINT_TOOLS:
        return [], 0
    linter = next(
        (t for t in _MARKDOWNLINT_TOOLS if runner.which(t.value)), None
    )
    if linter is None:
        return [], 0
    # UNIVERSAL_SUBSET routes run_tool to the bundled markdownlint config —
    # the right choice here, since a repo that declared a markdownlint config
    # would have selected markdownlint as the formatter (skipped above).
    return run_tool(
        mode=Mode.AUDIT,
        baseline=UNIVERSAL_SUBSET,
        unwrap=False,
        runner=runner,
        root=root,
        files=files,
        quiet=getattr(args, "quiet", False),
        tool_override=linter,
    )


def _dispatch_fix(
    args: argparse.Namespace, runner: ProcessRunner
) -> tuple[list[Event], int]:
    fs = OsFileSystem()
    root = repo_root(runner)
    baseline = detect_baseline(fs, root, args.baseline)
    files = _files_or_none(args)
    plugin_events = _maybe_plugin_missing_events(runner, fs, baseline, files, root)
    events, code = run_fix_cycle(
        runner=runner,
        root=root,
        baseline=baseline,
        unwrap=args.unwrap,
        files=files,
        quiet=getattr(args, "quiet", False),
    )
    # Mirror md-audit's complementary markdownlint lint pass. The fix cycle
    # only resolves what the chosen formatter (prettier) can auto-fix, so
    # without this pass a file violating only semantic MD### rules (MD040,
    # MD036, …) would make md-audit exit 1 while md-fix emitted a zero delta
    # and exited 0 — the two subcommands would disagree on the same repo.
    # The pass is read-only AUDIT, self-skips when the formatter already IS
    # markdownlint or no markdownlint binary is on PATH, and contributes its
    # exit code via max() so md-fix matches md-audit. Findings stay out of
    # the DELTA (which measures only the format pass's resolved/still_open/
    # new) and surface as their own FINDING events after it.
    lint_events, lint_code = _markdownlint_lint_pass(
        args, runner, root, baseline, files, Mode.AUDIT
    )
    return plugin_events + events + lint_events, max(code, lint_code)


def _maybe_plugin_missing_events(
    runner: ProcessRunner,
    fs: FileSystem,
    baseline: str,
    files: Sequence[str] | None,
    root: str,
) -> list[Event]:
    """Emit `plugin-missing` events when the selected tool would be mdformat
    and target files contain syntax requiring an absent plugin.

    No-op when:
    - The selected tool is not mdformat.
    - mdformat-gfm is already installed (covers the only auto-emitted check
      today; other plugins are detected by `probe.py` but not auto-flagged
      against file content).
    - No target file contains GFM-only syntax.

    Fires once per CLI invocation (before the formatter runs).
    """
    tool = select_tool(baseline, runner)
    if tool != Tool.MDFORMAT:
        return []
    installed = detect_installed_plugin_labels(runner)
    target_files = files if files is not None else tuple(list_markdown_files(runner, root))
    return emit_plugin_missing(_resolve_against_root(target_files, root), fs.read_text, installed)


def _dispatch_audit_frontmatter(
    args: argparse.Namespace, runner: ProcessRunner
) -> tuple[list[Event], int]:
    fs: FileSystem = OsFileSystem()
    root = repo_root(runner)
    files = _files_or_none(args)
    if files is None:
        files = list_markdown_files(runner, root)
    # Yamllint config precedence, highest first:
    #   1. `--yamllint-config <path>` — explicit user override, resolved
    #      against the invocation cwd (matches positional-file semantics
    #      in `_files_or_none`).
    #   2. Auto-discovered repo-root `.yamllint` / `.yamllint.yaml` /
    #      `.yamllint.yml` — mirrors yamllint's own standalone lookup
    #      so a repo that declares one of these drives the audit instead
    #      of the bundled fallback. Aligns md-audit-frontmatter with the
    #      markdown formatters: bundled configs are a fallback for repos
    #      that declare none, not an override that buries repo intent.
    #   3. None — routes `yaml_audit.audit_frontmatter` to the bundled
    #      `assets/configs/yamllint.yaml`.
    if args.yamllint_config is not None:
        yamllint_config = _resolve_config_against_cwd(args.yamllint_config)
    else:
        yamllint_config = _discover_repo_yamllint_config(fs, root)
    return audit_frontmatter(
        runner, fs, _resolve_against_root(files, root), config_path=yamllint_config,
    )


YAMLLINT_REPO_CANDIDATES: tuple[str, ...] = (
    ".yamllint",
    ".yamllint.yaml",
    ".yamllint.yml",
)
"""Filenames yamllint itself probes at the repo root when invoked
without `-c`. Order taken from the yamllint docs (`.yamllint` first,
then `.yamllint.yaml`, then `.yamllint.yml`). Kept as a module-level
constant so tests can assert the order without re-deriving it."""


def _discover_repo_yamllint_config(fs: FileSystem, root: str) -> str | None:
    """Return the absolute POSIX path of the first repo-root yamllint
    config that exists, or None when the repo declares none (caller
    falls back to the bundled config). The probe order mirrors yamllint's
    own standalone lookup so md-audit-frontmatter does not silently
    diverge from how a user running yamllint directly would resolve
    config."""
    for candidate in YAMLLINT_REPO_CANDIDATES:
        path = _posix_join(root, candidate)
        if fs.exists(path):
            return path
    return None


def _files_or_none(args: argparse.Namespace) -> Sequence[str] | None:
    """Return the args.files list (resolved to absolute paths) when
    non-empty; None means 'use the formatter's default glob over the
    repo root'.

    Relative positional file arguments are resolved against the
    invocation cwd (where the user actually ran the CLI), not against
    the detected repo root. The downstream pipeline runs the formatter
    with `cwd=root` — passing relative paths verbatim would target
    files under the WRONG directory whenever the user wasn't already
    at root (`cd docs && md-audit.py intro.md` is the canonical
    surprise). Resolving here makes the rest of the pipeline path-
    location agnostic.
    """
    files = getattr(args, "files", None)
    if files is None or len(files) == 0:
        return None
    invocation_cwd = os.getcwd()
    return tuple(
        _to_posix(path) if _is_absolute(path) else _posix_join(invocation_cwd, path)
        for path in files
    )


# Local aliases for the shared path helpers so internal cli.py call sites
# don't need to rename. See `paths.py` for the canonical implementations.
_is_absolute = is_absolute
_to_posix = to_posix
_posix_join = posix_join


def _resolve_against_root(files: Sequence[str], root: str) -> tuple[str, ...]:
    """Resolve any relative path in `files` against `root` so downstream
    file reads (FileSystem.read_text, audit_frontmatter, emit_plugin_missing)
    resolve to the same file the formatter sees when it runs with cwd=root.

    Absolute paths are normalized to forward slashes but not re-rooted;
    relative paths are joined with `root` via `_posix_join`. The result
    is uniformly POSIX-style — a Windows user passing
    `C:\\repo\\file.md` lands on `C:/repo/file.md`, so NDJSON output
    and command lines never mix backslash and forward-slash separators."""
    return tuple(
        _to_posix(path) if _is_absolute(path) else _posix_join(root, path)
        for path in files
    )


def _resolve_config_against_cwd(config: str | None) -> str | None:
    """Resolve `--yamllint-config` against the invocation cwd, mirroring
    how `_files_or_none` resolves positional file arguments. Relative
    paths therefore mean "relative to where the user typed the
    command", which is the only consistent answer when the CLI runs
    from a subdirectory. None passes through (use bundled fallback)."""
    if config is None:
        return None
    return _to_posix(config) if _is_absolute(config) else _posix_join(os.getcwd(), config)


_DISPATCH: dict[str, Callable[[argparse.Namespace, ProcessRunner], tuple[list[Event], int]]] = {
    "probe": _dispatch_probe,
    "recommend-tools": _dispatch_recommend,
    "md-audit": _dispatch_audit,
    "md-format": _dispatch_format,
    "md-fix": _dispatch_fix,
    "md-audit-frontmatter": _dispatch_audit_frontmatter,
}


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    runner: ProcessRunner = SubprocessRunner()
    events, exit_code = _DISPATCH[args.command](args, runner)
    _emit(events)
    return exit_code


if __name__ == "__main__":  # pragma: no cover — exercised via entry shims
    sys.exit(main())
