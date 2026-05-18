"""Audit / format orchestrator.

`run_tool` is the application service: it composes selector + commands +
bundled-config + process-runner into a single use case. The function returns
`(events, exit_code)` — the CLI layer is responsible for serialization and
exit. Pure aside from the injected `ProcessRunner`, which makes the whole
pipeline testable with `FakeProcessRunner`.

Exit-code contract:
    0  no output and clean exit (formatter passed)
    1  findings emitted or files changed
    2  formatter invocation error (returncode >= 2)
    3  no usable formatter on PATH
"""

from __future__ import annotations

import re
from collections.abc import Sequence

from .baseline import UNIVERSAL_SUBSET
from .bundled_config import bundled_config_for
from .commands import build_command
from .events import Event, EventType
from .modes import Mode
from .process import ProcessRunner
from .selector import select_tool
from .tools import Tool


_NO_TOOL_HINT = (
    "No usable formatter on PATH. Style baseline: {baseline}. "
    "See references/formatter-tools.md."
)


# Preamble-line patterns to drop under --quiet. These are formatter-emitted
# status / banner / summary lines that are not findings. A line passes the
# filter (is kept) when none of these patterns matches.
_PREAMBLE_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"^(markdownlint(?:-cli2)?|prettier|mdformat|dprint|remark|yamllint)[\s\-v]"),
    re.compile(r"^Finding:\s"),                       # markdownlint-cli2 banner
    re.compile(r"^Linting:\s"),                       # markdownlint-cli2 banner
    re.compile(r"^Summary:\s\d+\serror"),             # markdownlint-cli2 summary
    re.compile(r"^Checking formatting\.{3}"),         # prettier --check banner
    re.compile(r"^All matched files use Prettier"),   # prettier --check clean
    re.compile(r"^\(\d+\.?\d*ms\)$"),                 # prettier timing
)


def _is_preamble(line: str) -> bool:
    return any(p.search(line) for p in _PREAMBLE_PATTERNS)


def _emit_output_lines(
    raw: str, tool: str, mode: Mode, quiet: bool = False,
    dry_run: bool = False,
) -> list[Event]:
    """Convert formatter output into per-line events.

    `mode` decides FINDING (audit) vs CHANGED (format) vs WOULD_CHANGE (format + dry_run).
    `quiet` drops formatter preamble (banner / summary lines).
    """
    if mode == Mode.AUDIT:
        event_type = EventType.FINDING
    elif dry_run:
        event_type = EventType.WOULD_CHANGE
    else:
        event_type = EventType.CHANGED
    events: list[Event] = []
    for raw_line in raw.splitlines():
        line = raw_line.rstrip("\r").strip()
        if not line:
            continue
        if quiet and _is_preamble(line):
            continue
        events.append(Event(event_type, tool, line))
    return events


def _scope_command(
    cmd: list[str], files: Sequence[str] | None, tool: Tool
) -> list[str]:
    """Replace any glob arguments in the command with explicit files.

    When `files` is None, the command runs against the formatter's default
    glob (typically `**/*.md`). When `files` is provided, those positional
    args replace any glob token in the command — the formatter scopes to
    exactly the listed files.

    Detection of glob args is intentionally simple: any positional argument
    that contains `**` or ends with `.md` is treated as a glob and dropped;
    explicit files are appended after. Negative-glob args (`#node_modules`)
    are also dropped when scoping (they're meaningless on an explicit list).
    """
    if files is None:
        return cmd
    keep: list[str] = []
    for arg in cmd:
        if arg.startswith("#") or "**" in arg or arg.endswith(".md") or arg.endswith(".markdown") or arg == ".":
            continue
        keep.append(arg)
    keep.extend(files)
    return keep


def run_tool(
    mode: Mode,
    baseline: str,
    unwrap: bool,
    runner: ProcessRunner,
    root: str,
    files: Sequence[str] | None = None,
    quiet: bool = False,
    dry_run: bool = False,
) -> tuple[list[Event], int]:
    """Run the selected formatter and emit events.

    Parameters beyond mode/baseline/unwrap:
    - `files`: explicit list of file paths to audit/format. When None, the
      formatter runs against its default glob (typically `**/*.md`).
    - `quiet`: drop preamble lines from the formatter's output.
    - `dry_run`: in FORMAT mode, run the audit invocation instead and emit
      WOULD_CHANGE events. Ignored in AUDIT mode.
    """
    effective_mode = mode
    # dry_run on FORMAT mode delegates to the AUDIT invocation under the hood
    # (formatters expose this via --check / --frail), but the EVENT TYPE we
    # emit stays format-shaped (WOULD_CHANGE) to signal "what would change".
    if dry_run and mode == Mode.FORMAT:
        effective_mode = Mode.AUDIT

    tool = select_tool(baseline, runner)
    if tool is None:
        return (
            [Event(EventType.MISSING, "all", _NO_TOOL_HINT.format(baseline=baseline))],
            3,
        )

    events: list[Event] = []
    config_path: str | None = None
    config_source = "repo"
    if baseline == UNIVERSAL_SUBSET:
        candidate = bundled_config_for(tool)
        if candidate is not None:
            config_path = candidate
            config_source = "bundled"
            events.append(Event(EventType.BUNDLED_CONFIG, tool.value, candidate))
        else:
            config_source = "tool-default"

    cmd = build_command(tool, effective_mode, unwrap=unwrap, config_path=config_path)
    cmd = _scope_command(cmd, files, tool)
    events.append(
        Event(
            EventType.SELECTED,
            tool.value,
            {
                "baseline": baseline,
                "mode": mode.value,
                "unwrap": unwrap,
                "config_source": config_source,
                "cmd": " ".join(cmd),
                "files_scoped": len(files) if files is not None else None,
                "dry_run": dry_run,
            },
        )
    )

    result = runner.run(cmd, cwd=root)

    combined = (result.stdout + result.stderr).strip()
    if result.returncode == 0 and (effective_mode == Mode.AUDIT or not combined):
        events.append(Event(EventType.CLEAN, tool.value, f"{mode.value} passed"))
        return events, 0

    events.extend(
        _emit_output_lines(
            result.stdout + result.stderr, tool.value, mode, quiet=quiet, dry_run=dry_run
        )
    )

    if result.returncode >= 2:
        events.append(Event(EventType.ERROR, tool.value, {"exit": result.returncode}))
        return events, 2
    return events, 1


def run_fix_cycle(
    runner: ProcessRunner,
    root: str,
    baseline: str,
    unwrap: bool,
    files: Sequence[str] | None = None,
    quiet: bool = False,
) -> tuple[list[Event], int]:
    """One-shot loopback: audit → format → re-audit → emit DELTA.

    Always runs audit twice (pre + post format). The DELTA event reports
    resolved / still_open / new finding counts by file+line identity. When
    pre-audit is clean, format is skipped and DELTA reports zeros.

    Exit code reflects the post-audit state: 0 clean after fix, 1 findings
    still present, 2 formatter/audit error encountered in any phase.
    """
    pre_events, pre_exit = run_tool(
        Mode.AUDIT, baseline, unwrap, runner, root, files=files, quiet=quiet
    )

    pre_findings = _finding_keys(pre_events)

    if pre_exit >= 2:
        # Audit error — surface and bail; format would compound the failure.
        return pre_events, pre_exit

    if not pre_findings:
        # Already clean — skip format, emit zero delta.
        pre_events.append(
            Event(
                EventType.DELTA,
                "fix-cycle",
                {"resolved": 0, "still_open": 0, "new": 0},
            )
        )
        return pre_events, 0

    fmt_events, fmt_exit = run_tool(
        Mode.FORMAT, baseline, unwrap, runner, root, files=files, quiet=quiet
    )
    if fmt_exit >= 2:
        return pre_events + fmt_events, fmt_exit

    post_events, post_exit = run_tool(
        Mode.AUDIT, baseline, unwrap, runner, root, files=files, quiet=quiet
    )
    post_findings = _finding_keys(post_events)

    resolved = len(pre_findings - post_findings)
    still_open = len(pre_findings & post_findings)
    new = len(post_findings - pre_findings)

    delta_event = Event(
        EventType.DELTA,
        "fix-cycle",
        {"resolved": resolved, "still_open": still_open, "new": new},
    )

    all_events = pre_events + fmt_events + post_events + [delta_event]
    return all_events, post_exit


def _finding_keys(events: Sequence[Event]) -> set[str]:
    """Set of finding-line strings (used to compute fix-cycle deltas)."""
    return {
        str(e.detail)
        for e in events
        if e.event == EventType.FINDING and isinstance(e.detail, str)
    }
