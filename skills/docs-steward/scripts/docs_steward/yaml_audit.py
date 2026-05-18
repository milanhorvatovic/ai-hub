"""Audit YAML frontmatter + fenced YAML blocks across markdown files.

`audit_frontmatter(runner, fs, files, config_path=None)` is the application
service: walks each markdown file, extracts YAML-shaped blocks, pipes each
block's content into `yamllint -f parsable -s -`, parses yamllint's output,
and emits NDJSON events. Returns `(events, exit_code)` per the standard
service contract.

Exit-code semantics mirror the markdown audit pipeline:
    0  no findings (every block clean)
    1  at least one finding emitted
    2  yamllint invocation error
    3  yamllint not on PATH

yamllint output format ("parsable"): `stdin:LINE:COL: [LEVEL] message (rule)`.
The skill discards LINE:COL per the no-line-numbers convention and emits each
finding with `file + anchor` as locator — the anchor is the FrontmatterBlock
anchor (e.g. "frontmatter" or "yaml fence: <excerpt>").
"""

from __future__ import annotations

import re
from collections.abc import Sequence

from .bundled_config import bundled_config_for
from .events import Event, EventType
from .frontmatter import FrontmatterBlock, extract_blocks
from .fs import FileSystem
from .process import ProcessRunner
from .tools import Tool


_TOOL = Tool.YAMLLINT
_YAMLLINT_LINE = re.compile(
    r"^(?P<source>[^:]+):(?P<line>\d+):(?P<col>\d+):\s*\[(?P<level>\w+)\]\s*"
    r"(?P<msg>.*?)(?:\s*\((?P<rule>[^)]+)\))?$"
)


def _build_argv(config_path: str | None) -> list[str]:
    argv = ["yamllint", "-f", "parsable", "-s"]
    if config_path:
        argv.extend(["-c", config_path])
    argv.append("-")  # read from stdin
    return argv


def _parse_finding(raw: str, file_path: str, block: FrontmatterBlock) -> str:
    """Convert one yamllint parsable line into a human-friendly finding
    string. yamllint reports `stdin:LINE:COL: [LEVEL] message (rule)`; the
    skill replaces `stdin:LINE:COL` with `<file>:<anchor>` and keeps the
    level + message + rule intact."""
    match = _YAMLLINT_LINE.match(raw.strip())
    if not match:
        return f"{file_path}:{block.anchor} — {raw.strip()}"
    level = match.group("level")
    msg = match.group("msg")
    rule = match.group("rule") or "yamllint"
    return f"{file_path}:{block.anchor} — [{level}] {msg} ({rule})"


def _audit_one_block(
    runner: ProcessRunner,
    file_path: str,
    block: FrontmatterBlock,
    argv: Sequence[str],
) -> tuple[list[Event], int]:
    """Run yamllint on a single block; return (events, max_returncode)."""
    result = runner.run(list(argv), stdin=block.yaml_text)
    events: list[Event] = []
    output = (result.stdout + result.stderr).strip()
    for line in output.splitlines():
        stripped = line.rstrip("\r").strip()
        if not stripped:
            continue
        events.append(
            Event(EventType.FINDING, _TOOL.value, _parse_finding(stripped, file_path, block))
        )
    return events, result.returncode


def audit_frontmatter(
    runner: ProcessRunner,
    fs: FileSystem,
    files: Sequence[str],
    config_path: str | None = None,
) -> tuple[list[Event], int]:
    """Audit YAML blocks in every file in `files`. When `config_path` is
    None, the bundled fallback yamllint config is used; pass an explicit
    path (typically a repo's `.yamllint` / `.yamllint.yaml`) to override."""
    if runner.which(_TOOL.value) is None:
        return (
            [Event(EventType.MISSING, _TOOL.value, "yamllint not on PATH; install via: pipx install yamllint")],
            3,
        )

    resolved_config = config_path or bundled_config_for(_TOOL)
    argv = _build_argv(resolved_config)

    config_source = "repo" if config_path else ("bundled" if resolved_config else "tool-default")
    events: list[Event] = [
        Event(
            EventType.SELECTED,
            _TOOL.value,
            {
                "mode": "audit-frontmatter",
                "config_source": config_source,
                "config_path": resolved_config,
                "files_scanned": len(files),
            },
        )
    ]
    if resolved_config and config_source == "bundled":
        events.append(Event(EventType.BUNDLED_CONFIG, _TOOL.value, resolved_config))

    blocks_scanned = 0
    max_rc = 0
    file_errors: list[Event] = []

    for file_path in files:
        try:
            text = fs.read_text(file_path)
        except OSError as exc:
            file_errors.append(
                Event(
                    EventType.ERROR,
                    _TOOL.value,
                    {"file": file_path, "reason": f"{type(exc).__name__}: {exc}"},
                )
            )
            continue
        for block in extract_blocks(text):
            blocks_scanned += 1
            block_events, rc = _audit_one_block(runner, file_path, block, argv)
            events.extend(block_events)
            max_rc = max(max_rc, rc)

    events.extend(file_errors)

    if max_rc >= 2:
        events.append(Event(EventType.ERROR, _TOOL.value, {"exit": max_rc}))
        return events, 2

    finding_count = sum(1 for e in events if e.event == EventType.FINDING)
    if finding_count == 0 and not file_errors:
        events.append(
            Event(
                EventType.CLEAN,
                _TOOL.value,
                f"audit-frontmatter passed ({blocks_scanned} blocks across {len(files)} files)",
            )
        )
        return events, 0
    return events, 1
