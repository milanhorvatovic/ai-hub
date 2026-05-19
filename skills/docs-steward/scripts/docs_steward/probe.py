"""Inventory available formatters.

`probe_tools(runner)` returns `(events, exit_code)`. One `AVAILABLE` event
per supported tool on PATH (with version captured from `--version`); a
single `MISSING` event when no markdown FORMATTER is found. Exit code
follows the formatter-only contract: 0 when any tool in `REGISTRY` is
available, 3 when none. `yamllint` is complementary — its presence is
surfaced as `AVAILABLE` but does NOT satisfy the formatter contract,
so a host with only yamllint on PATH still exits 3 with the MISSING
event alongside the yamllint AVAILABLE entry.

`capture_version` lives here because the same shape applies to
`recommend_installs` — both modules call it to populate `installed` /
`available` event details from `--version` output. CR-stripping handles
Windows-shell line terminators uniformly.
"""

from __future__ import annotations

from .events import Event, EventType
from .plugins import probe_mdformat_plugins
from .process import ProcessRunner
from .tools import REGISTRY, SUPPORTED_TOOLS, Tool


_MISSING_HINT = (
    "No supported formatter on PATH. Install one of (binary name shown; "
    "the npm package name is in parens where it differs): "
    "markdownlint-cli2 (preferred markdownlint family), "
    "markdownlint (npm package: markdownlint-cli; legacy, same rule configs), "
    "prettier, mdformat, dprint, "
    "remark (npm package: remark-cli). "
    "Run `recommend-tools.py` for platform-specific install commands."
)


def capture_version(runner: ProcessRunner, tool: Tool) -> str:
    """First non-empty `--version` line, with `\\r` and surrounding `"` stripped.
    Empty string when the tool refuses to report a version."""
    result = runner.run([tool.value, "--version"])
    for raw in result.stdout.splitlines():
        line = raw.rstrip("\r").strip().strip('"')
        if line:
            return line
    return ""


def probe_tools(runner: ProcessRunner) -> tuple[list[Event], int]:
    """Inventory every supported tool on PATH.

    The MISSING / exit-3 decision is driven by formatter availability only
    (the tools in `REGISTRY`); yamllint is complementary — it lints YAML
    blocks via the `audit-frontmatter` pipeline and never participates in
    markdown formatter selection. An `AVAILABLE` event is still emitted
    for yamllint when present, but its presence does not by itself satisfy
    "any formatter on PATH" for the markdown audit pipeline.
    """
    events: list[Event] = []
    formatter_available = False
    mdformat_available = False
    formatter_tools = set(REGISTRY.keys())
    for tool in SUPPORTED_TOOLS:
        if runner.which(tool.value):
            events.append(
                Event(EventType.AVAILABLE, tool.value, capture_version(runner, tool))
            )
            if tool in formatter_tools:
                formatter_available = True
            if tool == Tool.MDFORMAT:
                mdformat_available = True
    if mdformat_available:
        # Append plugin-availability events for any known mdformat plugin.
        # probe_mdformat_plugins prefers the python interpreter resolved
        # from mdformat's shebang (via importlib.metadata) so pipx / uv
        # tool isolated installs are detected correctly; it falls back to
        # `pip show <package>` (pip / pip3 on PATH) only when the shebang
        # isn't readable (Windows .exe launchers, compiled wrappers).
        events.extend(probe_mdformat_plugins(runner))
    if not formatter_available:
        # Preserve any AVAILABLE events (e.g. yamllint) so callers can still
        # see what complementary tools exist while exiting 3 for the
        # markdown formatter contract.
        return events + [Event(EventType.MISSING, "all", _MISSING_HINT)], 3
    return events, 0
