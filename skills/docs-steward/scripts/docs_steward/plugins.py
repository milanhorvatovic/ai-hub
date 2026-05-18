"""mdformat plugin detection + GFM-syntax sniffing.

mdformat's default install handles CommonMark only. GitHub-flavored markdown
features (tables, task lists, strikethrough, autolinks) require the
`mdformat-gfm` plugin (and others depending on syntax used). Without the
plugin, mdformat silently passes through unrecognized syntax — the rewrite is
incomplete but emits no warning.

`probe_mdformat_plugins(runner)` returns the list of installed mdformat
plugin names + versions. `needs_gfm(text)` is a pure-Python regex sniffer
that returns True when the text contains syntax requiring `mdformat-gfm`.

Used by:
- `probe.probe_tools`: emits PLUGIN_AVAILABLE events when mdformat is on PATH
  and any known plugin is detected.
- `runner.run_tool`: when mdformat is selected and a target file contains GFM
  syntax but `mdformat-gfm` is not installed, emits a PLUGIN_MISSING event.
"""

from __future__ import annotations

import re
from collections.abc import Sequence

from .events import Event, EventType
from .process import ProcessRunner


# Known mdformat plugin packages the probe checks for. Each maps to a short
# label used in event details. Adding a plugin = one tuple entry; no other
# module changes needed.
KNOWN_PLUGINS: tuple[tuple[str, str], ...] = (
    ("mdformat-gfm", "gfm"),
    ("mdformat-tables", "tables"),
    ("mdformat-frontmatter", "frontmatter"),
    ("mdformat-footnote", "footnote"),
    ("mdformat-toc", "toc"),
)


# Regex sniffers for GFM-only syntax. Conservative: false positives on plain
# CommonMark are acceptable (PLUGIN_MISSING is INFO-shaped, not blocking);
# false negatives miss real plugin-missing cases. Tuned for the common syntax.
_GFM_TABLE = re.compile(r"^\s*\|.*\|.*\|\s*$", re.MULTILINE)
_GFM_TASK_LIST = re.compile(r"^\s*[-*+]\s+\[[ xX]\]\s", re.MULTILINE)
_GFM_STRIKETHROUGH = re.compile(r"~~[^\s~][^~]*~~")
_GFM_AUTOLINK = re.compile(r"(?<!\]\()https?://\S+(?![^\[]*\])")


def probe_mdformat_plugins(runner: ProcessRunner) -> list[Event]:
    """For each known mdformat plugin, run `<plugin> --version` (the plugin
    binary if it ships one, else `pip show`). Emit PLUGIN_AVAILABLE per hit.

    Returns events only — caller decides whether/how to surface them.
    """
    events: list[Event] = []
    pip = runner.which("pip") or runner.which("pip3")
    if pip is None:
        # No pip available — cannot probe Python packages reliably.
        return events
    for package, label in KNOWN_PLUGINS:
        result = runner.run([pip, "show", package])
        if result.returncode != 0:
            continue
        version = _parse_pip_show_version(result.stdout)
        if version:
            events.append(
                Event(
                    EventType.PLUGIN_AVAILABLE,
                    "mdformat",
                    {"plugin": label, "package": package, "version": version},
                )
            )
    return events


def _parse_pip_show_version(stdout: str) -> str:
    for line in stdout.splitlines():
        if line.lower().startswith("version:"):
            return line.split(":", 1)[1].strip()
    return ""


def needs_gfm(text: str) -> bool:
    """True when `text` contains syntax that mdformat handles only with the
    `mdformat-gfm` plugin installed. Tables / task lists / strikethrough /
    bare autolinks all qualify."""
    return any(
        pattern.search(text)
        for pattern in (_GFM_TABLE, _GFM_TASK_LIST, _GFM_STRIKETHROUGH, _GFM_AUTOLINK)
    )


def detect_installed_plugin_labels(runner: ProcessRunner) -> set[str]:
    """Set of installed plugin labels (e.g. {'gfm', 'tables'}). Pure
    convenience over probe_mdformat_plugins for callers that need a quick
    membership check rather than the full event list."""
    return {
        event.detail["plugin"]  # type: ignore[index]
        for event in probe_mdformat_plugins(runner)
        if isinstance(event.detail, dict) and "plugin" in event.detail
    }


def emit_plugin_missing(
    files: Sequence[str], read_text: "Callable[[str], str]",  # noqa: F821 — fwd ref
    installed_labels: set[str],
) -> list[Event]:
    """For each file whose content requires a plugin not in `installed_labels`,
    emit a PLUGIN_MISSING event. `read_text` is a callable that returns the
    text content for a given path (typically FileSystem.read_text) — kept as
    a callable parameter so callers don't need to plumb a FileSystem here.

    Only `mdformat-gfm` is checked today; other plugins (tables/footnote/etc.)
    have narrower triggers and are out of scope for the auto-emit path.
    """
    if "gfm" in installed_labels:
        return []
    events: list[Event] = []
    for path in files:
        try:
            text = read_text(path)
        except OSError:
            continue
        if needs_gfm(text):
            events.append(
                Event(
                    EventType.PLUGIN_MISSING,
                    "mdformat",
                    {
                        "plugin": "gfm",
                        "package": "mdformat-gfm",
                        "file": path,
                        "reason": "file contains GFM syntax (tables / task lists / strikethrough / autolinks)",
                    },
                )
            )
    return events
