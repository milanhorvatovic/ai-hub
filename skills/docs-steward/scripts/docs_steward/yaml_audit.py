"""Audit YAML frontmatter + fenced YAML blocks across markdown files.

`audit_frontmatter(runner, fs, files, config_path=None)` is the application
service: walks each markdown file, extracts YAML-shaped blocks, pipes each
block's content into `yamllint -f parsable -s -`, parses yamllint's output,
and emits NDJSON events. Returns `(events, exit_code)` per the standard
service contract.

Exit-code semantics mirror the markdown audit pipeline:
    0  no findings (every block clean) and no file errors
    1  at least one yamllint finding emitted
    2  yamllint invocation error OR a target file was unreadable
       (per-file ERROR events emit inline; aggregate maps to exit 2
       so consumers don't misread it as "lint findings exist")
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


def _parse_finding(raw: str, file_path: str, block: FrontmatterBlock) -> tuple[str, bool]:
    """Convert one yamllint parsable line into a human-friendly finding
    string. yamllint reports `stdin:LINE:COL: [LEVEL] message (rule)`; the
    skill replaces `stdin:LINE:COL` with `<file>:<anchor>` and keeps the
    level + message + rule intact.

    Returns (finding_string, matched) where `matched` is True when the
    input parsed as a real yamllint parsable line and False when the
    fallback (raw passthrough) was used. The flag lets the caller
    distinguish "yamllint produced a real finding" from "yamllint emitted
    noise we wrapped as a finding" — a yamllint config error written to
    stderr is the latter case.
    """
    match = _YAMLLINT_LINE.match(raw.strip())
    if not match:
        return f"{file_path}:{block.anchor} — {raw.strip()}", False
    level = match.group("level")
    msg = match.group("msg")
    rule = match.group("rule") or "yamllint"
    return f"{file_path}:{block.anchor} — [{level}] {msg} ({rule})", True


def _audit_one_block(
    runner: ProcessRunner,
    file_path: str,
    block: FrontmatterBlock,
    argv: Sequence[str],
) -> tuple[list[Event], int, int]:
    """Run yamllint on a single block; return (events, returncode,
    matched_count) where matched_count is the number of output lines
    that parsed as proper yamllint parsable findings (vs fallback)."""
    result = runner.run(list(argv), stdin=block.yaml_text)
    events: list[Event] = []
    matched_count = 0
    output = (result.stdout + result.stderr).strip()
    for line in output.splitlines():
        stripped = line.rstrip("\r").strip()
        if not stripped:
            continue
        finding, matched = _parse_finding(stripped, file_path, block)
        if matched:
            matched_count += 1
        events.append(Event(EventType.FINDING, _TOOL.value, finding))
    return events, result.returncode, matched_count


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
    invocation_failure_rc = 0
    any_file_error = False

    for file_path in files:
        try:
            text = fs.read_text(file_path)
        except OSError as exc:
            # Emit per-file ERROR inline so consumers reading the event
            # stream in order see the failure adjacent to (or before) the
            # FINDING events from later files. Deferring with a post-loop
            # extend put all error events at the bottom, after findings
            # from files that the loop processed successfully later — a
            # surprise for ordering-sensitive consumers.
            events.append(
                Event(
                    EventType.ERROR,
                    _TOOL.value,
                    {"file": file_path, "reason": f"{type(exc).__name__}: {exc}"},
                )
            )
            any_file_error = True
            continue
        for block in extract_blocks(text):
            blocks_scanned += 1
            block_events, rc, matched_count = _audit_one_block(
                runner, file_path, block, argv,
            )
            events.extend(block_events)
            if rc >= 2 and matched_count == 0:
                # True yamllint invocation failure: non-zero exit AND zero
                # output lines parsed as real yamllint findings. yamllint
                # -s exits 2 whenever a warning-level finding fires, but
                # in that case `matched_count` is non-zero (the warning
                # parsed against _YAMLLINT_LINE). Distinguishing the two
                # avoids classifying every warning-only audit as exit 2 +
                # ERROR; only true invocation failures (config error,
                # python traceback, missing schema) take this path.
                invocation_failure_rc = max(invocation_failure_rc, rc)

    if invocation_failure_rc >= 2:
        events.append(
            Event(EventType.ERROR, _TOOL.value, {"exit": invocation_failure_rc}),
        )
        return events, 2

    finding_count = sum(1 for e in events if e.event == EventType.FINDING)
    if finding_count == 0 and not any_file_error:
        events.append(
            Event(
                EventType.CLEAN,
                _TOOL.value,
                f"audit-frontmatter passed ({blocks_scanned} blocks across {len(files)} files)",
            )
        )
        return events, 0
    if finding_count == 0 and any_file_error:
        # No real findings — only per-file read failures (file deleted,
        # encoding errors, permission). Exit 1 would advertise "findings
        # present" to a CI consumer; exit 2 (invocation/setup error)
        # tells the truth: yamllint was healthy but the audit couldn't
        # complete against every requested file.
        return events, 2
    return events, 1
