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
import os.path
import sys
from collections.abc import Iterable, Sequence
from typing import Callable

from .baseline import detect_baseline
from .discovery import list_markdown_files
from .emit import serialize
from .events import Event
from .fs import FileSystem, OsFileSystem
from .modes import Mode
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
        help="Path to a yamllint config; defaults to the bundled fallback.",
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
    return plugin_events + events, code


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
    return plugin_events + events, code


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
    yamllint_config = _resolve_config_against_root(args.yamllint_config, root)
    return audit_frontmatter(
        runner, fs, _resolve_against_root(files, root), config_path=yamllint_config,
    )


def _files_or_none(args: argparse.Namespace) -> Sequence[str] | None:
    """Return the args.files list when non-empty; None means 'use the
    formatter's default glob over the repo root'."""
    files = getattr(args, "files", None)
    if files is None or len(files) == 0:
        return None
    return tuple(files)


def _resolve_against_root(files: Sequence[str], root: str) -> tuple[str, ...]:
    """Resolve any relative path in `files` against `root` so downstream
    file reads (FileSystem.read_text, audit_frontmatter, emit_plugin_missing)
    resolve to the same file the formatter sees when it runs with cwd=root.

    Absolute paths pass through unchanged; relative paths are joined with
    `root` via os.path.join (native separator on the host — Python file
    APIs accept either separator on Windows). Idempotent for paths produced
    by discovery.list_markdown_files (which already returns absolute, POSIX
    -joined paths)."""
    return tuple(
        path if os.path.isabs(path) else os.path.join(root, path) for path in files
    )


def _resolve_config_against_root(config: str | None, root: str) -> str | None:
    """Same resolution rule as `_resolve_against_root`, applied to a single
    optional config path (e.g. `--yamllint-config .yamllint`). None passes
    through so the caller can still signal "use the bundled fallback"."""
    if config is None:
        return None
    return config if os.path.isabs(config) else os.path.join(root, config)


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
