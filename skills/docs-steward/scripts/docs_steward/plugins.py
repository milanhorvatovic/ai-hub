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
- `cli._maybe_plugin_missing_events`: when mdformat is selected and a target
  file contains GFM syntax but `mdformat-gfm` is not installed, emits a
  PLUGIN_MISSING event before the formatter runs (so consumers see the
  warning ahead of the audit findings). `runner.run_tool` itself does not
  perform plugin detection; the check is hoisted to the CLI dispatcher so
  it can pass the resolved target files in.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Sequence

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
    """Detect installed mdformat plugins via the Python interpreter that
    actually backs the `mdformat` binary, not via the first `pip` / `pip3`
    on PATH.

    mdformat is commonly installed via pipx, `uv tool`, or a dedicated
    venv, which place mdformat (and its plugins) in an isolated environment
    where the system `pip` cannot see them. Calling `pip show <package>`
    against an unrelated interpreter produced both false-negative
    PLUGIN_AVAILABLE events (the plugin IS installed where mdformat lives)
    and false-positive PLUGIN_MISSING events later in the pipeline.

    Strategy:
    1. Resolve the `mdformat` binary on PATH via `runner.which`.
    2. Read its shebang to extract the interpreter path (handles the
       `/usr/bin/env <interp>` form by returning the trailing argument so
       subprocess resolves it via PATH).
    3. For each plugin in `KNOWN_PLUGINS`, invoke that interpreter with
       `python -c "import importlib.metadata as m; print(m.version(...))"`
       to read the installed version. Non-zero exit means the plugin is
       absent in this environment (no event emitted).

    Falls back to the legacy `pip` / `pip3` strategy when the shebang
    cannot be read (e.g. on Windows where mdformat is launched via a
    PEP-397 / pipx-managed `.exe` shim rather than a shebang script).
    Returns an empty list when neither strategy can run.
    """
    interpreter = _resolve_mdformat_interpreter(runner)
    if interpreter is not None:
        return _probe_via_interpreter(runner, interpreter)
    return _probe_via_pip_fallback(runner)


def _resolve_mdformat_interpreter(runner: ProcessRunner) -> str | None:
    """Return the path / executable name of the Python interpreter that
    runs mdformat, by reading the binary's shebang. Returns None when
    mdformat is absent, the file is not a shebang script (Windows .exe
    launcher / compiled binary), or the shebang is malformed."""
    mdformat_path = runner.which("mdformat")
    if mdformat_path is None:
        return None
    try:
        with open(mdformat_path, "rb") as handle:
            first_line = handle.readline(1024)
    except OSError:
        return None
    if not first_line.startswith(b"#!"):
        return None
    # errors="replace" cannot raise UnicodeDecodeError; a stray non-UTF-8
    # byte degrades to U+FFFD and `line.split()` still produces something
    # the parts[] checks can reject downstream.
    line = first_line[2:].decode("utf-8", errors="replace").strip()
    parts = line.split()
    if not parts:
        return None
    head = parts[0]
    # `/usr/bin/env python3` style — return the first non-flag argument
    # after `env` so the subprocess can resolve it via PATH itself. Modern
    # shebangs use `env -S <flags> <interp>` (the -S "split" flag lets
    # multiple args pass through); naive parts[1] would return the
    # literal `-S` and the subsequent interpreter probe would fail.
    if head.endswith("env"):
        for arg in parts[1:]:
            if not arg.startswith("-"):
                return arg
        return None
    return head


def _probe_via_interpreter(runner: ProcessRunner, interpreter: str) -> list[Event]:
    events: list[Event] = []
    for package, label in KNOWN_PLUGINS:
        result = runner.run(
            [
                interpreter, "-c",
                f"import importlib.metadata as m; print(m.version({package!r}))",
            ]
        )
        if result.returncode != 0:
            continue
        version = result.stdout.strip()
        if version:
            events.append(
                Event(
                    EventType.PLUGIN_AVAILABLE,
                    "mdformat",
                    {"plugin": label, "package": package, "version": version},
                )
            )
    return events


def _probe_via_pip_fallback(runner: ProcessRunner) -> list[Event]:
    """Last-resort probe used when the mdformat shebang is unavailable
    (e.g. Windows .exe shims). Inherits the original ambient-pip drift
    — its results are only meaningful when mdformat and pip resolve to
    the same Python."""
    events: list[Event] = []
    pip = runner.which("pip") or runner.which("pip3")
    if pip is None:
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
    files: Sequence[str], read_text: Callable[[str], str],
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
        except (OSError, UnicodeDecodeError):
            # Skip files we cannot inspect at all. OSError covers
            # FileNotFoundError / PermissionError / IsADirectoryError;
            # UnicodeDecodeError fires when the target file isn't valid
            # UTF-8 (a ValueError subclass, NOT OSError). This check
            # runs in the CLI preamble — letting either exception
            # propagate would crash the entire md-audit / md-format
            # invocation before the formatter even starts.
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
