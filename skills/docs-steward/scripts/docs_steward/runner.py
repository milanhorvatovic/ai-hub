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
from .paths import is_absolute, posix_join
from .process import ProcessRunner
from .selector import baseline_belongs_to_tool, select_tool
from .tools import Tool


_NO_TOOL_HINT = (
    "No usable formatter on PATH. Style baseline: {baseline}. "
    "Run `recommend-tools.py` for platform-specific install commands."
)


# Preamble-line patterns to drop under --quiet. These are formatter-emitted
# status / banner / summary lines that are not findings. A line passes the
# filter (is kept) when none of these patterns matches. The version-banner
# pattern requires whitespace followed by an optional `v` and a digit so
# it matches the real "prettier 3.2.5" / "markdownlint-cli2 v0.13.0" shape
# without false-positiving on finding lines that happen to start with a
# tool name + path delimiter (e.g. `prettier-v3.md:1 MD040 ...` or
# `remark-v1.md:5 MD040 ...`).
_PREAMBLE_PATTERNS: tuple[re.Pattern[str], ...] = (
    # Version banner: tool name + whitespace + optional `v` + dotted
    # numeric version + end-of-line. Anchoring `\s*$` after the
    # version-shaped token rejects finding lines whose path begins
    # with `<tool> <digit>` (e.g. `prettier 3.md:1 MD040 ...` — paths
    # can contain spaces, see round-8a regression). The version-shape
    # pattern accepts `prettier 3`, `prettier 3.2`, `prettier 3.2.5`,
    # `prettier v3.2.5` — every form the supported tools actually emit.
    re.compile(
        r"^(markdownlint(?:-cli2)?|prettier|mdformat|dprint|remark|yamllint)\s+v?\d+(?:\.\d+)*\s*$",
    ),
    # markdownlint-cli2's startup banner carries a trailing engine version in
    # parens (`markdownlint-cli2 v0.22.1 (markdownlint v0.40.0)`), so the
    # generic version-banner pattern above (anchored `\s*$` after the version)
    # doesn't catch it. Match it explicitly — specific enough not to swallow a
    # finding line, which always begins with a `path:line` locator.
    re.compile(r"^markdownlint-cli2 v[\d.]+\s+\(markdownlint v"),
    re.compile(r"^Finding:\s"),                       # markdownlint-cli2 banner
    re.compile(r"^Linting:\s"),                       # markdownlint-cli2 banner
    re.compile(r"^Summary:\s\d+\serror"),             # markdownlint-cli2 summary
    re.compile(r"^Checking formatting\.{3}"),         # prettier --check banner
    re.compile(r"^All matched files use Prettier"),   # prettier --check clean
    re.compile(r"^(?:\[warn\]\s+)?Code style issues found"),  # prettier --check summary (also prefixed)
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


# argv flags that take a value as the next token. _scope_command must
# NOT drop the value half even when that value happens to match the
# glob-arg heuristic (e.g. `--config notes.md` would otherwise leave
# `--config` orphaned and the formatter would consume the next flag
# as the config path).
_VALUE_BEARING_FLAGS: frozenset[str] = frozenset({
    "--config",
    "-c",
    "--ignore-path",
})


def _scope_command(
    cmd: list[str], files: Sequence[str] | None
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

    Value halves of preceding value-bearing flags (`--config <path>`,
    `-c <path>`, `--ignore-path <path>`) are NEVER dropped, even when the
    value matches the glob-arg heuristic — a `--config notes.md` argv
    pair must survive scoping intact or the formatter ends up consuming
    the next flag as its config path.

    A POSIX `--` separator is inserted between the kept flags and the
    explicit files so that a path beginning with `-` / `--` (e.g.
    `./--draft.md`) is treated as a positional file rather than a flag by
    the underlying formatter. All supported tools accept `--`, so no
    per-tool branching is needed.
    """
    if files is None:
        return cmd
    keep: list[str] = []
    prev: str | None = None
    for arg in cmd:
        glob_like = (
            arg.startswith("#")
            or "**" in arg
            or arg.endswith(".md")
            or arg.endswith(".markdown")
            or arg == "."
        )
        if glob_like and prev not in _VALUE_BEARING_FLAGS:
            prev = arg
            continue
        keep.append(arg)
        prev = arg
    keep.append("--")
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
    tool_override: Tool | None = None,
) -> tuple[list[Event], int]:
    """Run the selected formatter and emit events.

    Parameters beyond mode/baseline/unwrap:
    - `files`: explicit list of file paths to audit/format. When None, the
      formatter runs against its default glob (typically `**/*.md`).
    - `quiet`: drop preamble lines from the formatter's output.
    - `dry_run`: in FORMAT mode, run the audit invocation instead and emit
      WOULD_CHANGE events. Ignored in AUDIT mode.
    - `tool_override`: run this specific tool instead of selecting one from
      `baseline`. Used for the complementary markdownlint lint pass the CLI
      runs alongside a non-markdownlint formatter in audit mode (pass
      `baseline=UNIVERSAL_SUBSET` with the override to pick up the tool's
      bundled config).
    """
    effective_mode = mode
    # dry_run on FORMAT mode delegates to the AUDIT invocation under the hood
    # (formatters expose this via --check / --frail), but the EVENT TYPE we
    # emit stays format-shaped (WOULD_CHANGE) to signal "what would change".
    if dry_run and mode == Mode.FORMAT:
        effective_mode = Mode.AUDIT

    tool = tool_override if tool_override is not None else select_tool(baseline, runner)
    if tool is None:
        return (
            [Event(EventType.MISSING, "all", _NO_TOOL_HINT.format(baseline=baseline))],
            3,
        )

    events: list[Event] = []
    config_path: str | None = None
    config_source = "repo"
    # Deferred until after SELECTED is appended below so the event order
    # matches yaml_audit.audit_frontmatter (SELECTED first, then optional
    # BUNDLED_CONFIG). Streaming consumers can rely on the first event of
    # any pipeline being SELECTED — which carries the run parameters —
    # without conditionally peeking for an earlier BUNDLED_CONFIG.
    bundled_event: Event | None = None
    if baseline == UNIVERSAL_SUBSET:
        candidate = bundled_config_for(tool)
        if candidate is not None:
            config_path = candidate
            config_source = "bundled"
            bundled_event = Event(EventType.BUNDLED_CONFIG, tool.value, candidate)
        else:
            config_source = "tool-default"
    elif baseline_belongs_to_tool(baseline, tool):
        # Explicit baseline (auto-detected at root or supplied via --baseline)
        # belongs to the selected tool's family — forward it as the tool's
        # --config so a config that lives outside cwd or under a subdirectory
        # is still honoured. Relative paths resolve against `root` (the
        # directory the formatter runs in) so the contract matches SKILL.md's
        # claim that the baseline is "passed verbatim to the chosen formatter".
        # Forward-slash join (regardless of host) keeps the command line
        # consistent on Windows where os.path.join would otherwise insert
        # backslashes that diverge from discovery's POSIX-normalized paths.
        # is_absolute treats both POSIX-leading-slash and Windows drive-
        # letter form (`C:\` / `C:/`) as absolute; absolute paths are
        # normalized to forward slashes so a Windows --baseline
        # C:\repo\.prettierrc lands in selected.detail.cmd as
        # C:/repo/.prettierrc. The helper is shared with cli.py to keep
        # the absolute / relative decision uniform across modules.
        if is_absolute(baseline):
            config_path = baseline.replace("\\", "/")
        else:
            config_path = posix_join(root, baseline)
        # config_source stays "repo" — the path came from the repo / caller,
        # not a bundled fallback or tool default.
    # else: baseline matched a different tool's family (or .editorconfig);
    # the selected tool's CommandTemplate either has config_flag=None
    # (mdformat / dprint / remark — discover-from-cwd) or already runs with
    # cwd=root and will find the baseline via its own discovery.

    cmd = build_command(tool, effective_mode, unwrap=unwrap, config_path=config_path)
    cmd = _scope_command(cmd, files)
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
    if bundled_event is not None:
        events.append(bundled_event)

    result = runner.run(cmd, cwd=root)

    # CLEAN decision and event-stream parsing both key on STDOUT only in
    # FORMAT mode. Formatters emit per-file change records on stdout and
    # reserve stderr for banner / deprecation warnings / debug output —
    # consulting stderr for CLEAN/CHANGED leaked that noise as spurious
    # CHANGED events and suppressed CLEAN when a successful format
    # happened to print a deprecation warning. In AUDIT mode we still
    # concatenate stderr because some formatters (markdownlint-cli2's
    # exit-1 banner; remark's --frail messages) put real findings there.
    stdout_trimmed = result.stdout.strip()
    if result.returncode == 0 and (effective_mode == Mode.AUDIT or not stdout_trimmed):
        events.append(Event(EventType.CLEAN, tool.value, f"{mode.value} passed"))
        return events, 0

    # Parse the tool's stdout into FINDING / CHANGED / WOULD_CHANGE
    # events. Choice of stream by mode + rc:
    #   - AUDIT, rc == 1: stdout + stderr — some tools emit real
    #     findings on stderr (markdownlint-cli2 exit-1 banner, remark
    #     --frail messages).
    #   - AUDIT, rc >= 2 or rc < 0: stdout only. stderr is attached to
    #     the ERROR event below; including it in the FINDING stream too
    #     would duplicate the diagnostic.
    #   - FORMAT, any rc: stdout only. stderr in FORMAT is banner /
    #     deprecation noise (round 8g).
    # SKILL.md's contract says the tool's output should be surfaced as
    # events before any ERROR — keeping the parse here (rather than
    # short-circuiting on rc >= 2) preserves stdout diagnostics for
    # consumers, while the duplication that round 10 hoisted past is
    # avoided by NOT concatenating stderr on the error path.
    is_error_rc = result.returncode >= 2 or result.returncode < 0
    if effective_mode == Mode.FORMAT or is_error_rc:
        output_for_events = result.stdout
    else:
        output_for_events = result.stdout + result.stderr
    events.extend(
        _emit_output_lines(
            output_for_events, tool.value, mode, quiet=quiet, dry_run=dry_run
        )
    )

    if is_error_rc:
        # Attach the tool's stderr to the ERROR detail when the run
        # failed. Successful runs filter stderr out of the event stream
        # (round 8g) to avoid leaking deprecation warnings / banner
        # noise as spurious CHANGED events, but the FAILURE path needs
        # those bytes — a `prettier --write` config-error, an mdformat
        # plugin crash, a Python traceback from yamllint all surface on
        # stderr with empty stdout, so a bare {"exit": N} ERROR gave
        # consumers no actionable signal. stderr is included verbatim
        # (with surrounding whitespace stripped) when present.
        detail: dict[str, object] = {"exit": result.returncode}
        stderr_text = result.stderr.strip()
        if stderr_text:
            detail["stderr"] = stderr_text
        events.append(Event(EventType.ERROR, tool.value, detail))
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

    Runs audit at least once. When the pre-audit is already clean (no
    FINDING events), the format and re-audit phases are skipped entirely
    and a zeroed DELTA is emitted. Otherwise audit is invoked twice — once
    before format and once after — and the DELTA event reports resolved /
    still_open / new finding counts by file+line identity. If the pre-audit
    or the format phase errors out (exit ≥ 2), the cycle bails early and
    the post-audit is not run.

    Exit code reflects the latest completed phase: 0 clean after fix (or
    clean pre-audit), 1 findings still present, 2 formatter/audit error.
    """
    pre_events, pre_exit = run_tool(
        Mode.AUDIT, baseline, unwrap, runner, root, files=files, quiet=quiet
    )

    pre_findings = _finding_keys(pre_events)

    if pre_exit >= 2:
        # Audit error — surface and bail; format would compound the failure.
        return pre_events, pre_exit

    if pre_exit == 0 and not pre_findings:
        # Already clean — skip format, emit zero delta. The `pre_exit == 0`
        # guard is load-bearing: a formatter that exited 1 but whose output
        # the line-parser did not turn into FINDING events (custom output
        # shape, parser regression) would otherwise collapse to delta=0,0,0
        # and exit 0 here — silently masking the failed audit. Forwarding
        # pre_exit instead preserves the failure signal.
        pre_events.append(
            Event(
                EventType.DELTA,
                "fix-cycle",
                {"resolved": 0, "still_open": 0, "new": 0},
            )
        )
        return pre_events, 0

    if not pre_findings:
        # pre_exit == 1 with empty parsed findings — propagate the failure;
        # the formatter said something is wrong but the line-parser produced
        # nothing actionable. Skipping format avoids compounding the issue.
        return pre_events, pre_exit

    fmt_events, fmt_exit = run_tool(
        Mode.FORMAT, baseline, unwrap, runner, root, files=files, quiet=quiet
    )
    if fmt_exit >= 2:
        return pre_events + fmt_events, fmt_exit

    post_events, post_exit = run_tool(
        Mode.AUDIT, baseline, unwrap, runner, root, files=files, quiet=quiet
    )
    if post_exit >= 2:
        # Post-audit errored before producing FINDING events. Computing a
        # DELTA at this point would difference `pre_findings` against an
        # empty `post_findings` set and misreport every pre-finding as
        # "resolved" — the audit didn't say they were fixed, the parser
        # just had nothing to compare against. Mirror the pre-audit /
        # format-phase error guards: surface the events without DELTA and
        # forward the failure exit code.
        return pre_events + fmt_events + post_events, post_exit
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


# Strip ONLY the leading `<path>.{md,markdown}:LINE[:COL][-LINE:COL]` prefix —
# anchored at start of line so a URL with a port (`https://host:8080/foo`)
# embedded later in the message text isn't mistaken for a line/column number
# and stripped. The captured path uses `.+?` (not `\S+?`) so paths
# containing spaces (e.g. `my docs/guide.md:42:3 MD040 ...`) are captured
# whole; `.` does not match newline by default, so the match is still
# bounded to a single line. The captured path is preserved via \1.
_LINE_COL_PATTERN = re.compile(
    r"^(.+?\.(?:md|markdown)):\d+(?::\d+)?(?:-\d+:\d+)?",
    re.IGNORECASE,
)
_QUOTED_FRAGMENT_PATTERN = re.compile(r'\s*"[^"]*"\s*$')


def _normalize_finding_key(detail: str) -> str:
    """Strip line/column numbers and any trailing quoted-fragment excerpt
    from a finding line so an unfixed finding produces the same key
    before and after a format pass shifts its line position.

    Without normalization, an md-fix pre/post audit would compute
    `still_open = pre & post` against raw strings like
    `README.md:42:3 MD040 ...` vs `README.md:38:3 MD040 ...` (same
    finding, different line after reflow) and count the same finding
    as one `resolved` + one `new` instead of one `still_open`.

    Handles the three line-position shapes the supported formatters emit:
    - markdownlint: `path:LINE:COL MD### ...`
    - remark:       `path:LINE:COL-LINE:COL warning ...`
    - prettier / mdformat / dprint emit `path` only — already stable.

    The pattern is anchored to the start of the line and requires the
    leading path to end with `.md` / `.markdown`, so a URL with a port
    (e.g. `https://host:8080/foo`) embedded in the finding text is not
    mistaken for `:LINE:COL` and silently rewritten.
    """
    normalized = _LINE_COL_PATTERN.sub(r"\1", detail)
    normalized = _QUOTED_FRAGMENT_PATTERN.sub("", normalized).strip()
    return normalized


def _finding_keys(events: Sequence[Event]) -> set[str]:
    """Set of normalized finding keys (used to compute fix-cycle deltas)."""
    return {
        _normalize_finding_key(e.detail)
        for e in events
        if e.event == EventType.FINDING and isinstance(e.detail, str)
    }
