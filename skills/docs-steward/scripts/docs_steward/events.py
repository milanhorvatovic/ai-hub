"""NDJSON event vocabulary.

`Event` is the single value type emitted by every service in this package.
The CLI layer serializes events to NDJSON; tests assert against `Event` instances
directly, never against serialized strings. Detail payloads are typed loosely
(`object`) because the schema is per-event-type — see EventType docstring.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class EventType(str, Enum):
    """Every NDJSON event the skill can emit. Detail-payload shape per type:

    - AVAILABLE / INSTALLED / BUNDLED_CONFIG: detail is a string (version / path).
    - MISSING / CLEAN / VERDICT: detail is a string (human-readable message).
    - RECOMMEND: detail is a dict {"priority_rank": int, "install_options": list[str]}.
    - SELECTED: detail is pipeline-specific. Markdown formatter pipeline
      (`md-audit` / `md-format` / `md-fix`) emits
      {"baseline", "mode", "unwrap", "config_source", "cmd",
       "files_scoped", "dry_run"}. Frontmatter audit pipeline
      (`md-audit-frontmatter`) emits {"mode": "audit-frontmatter",
       "config_source", "config_path", "files_scanned"} — no `baseline`,
      `unwrap`, `cmd`, `files_scoped`, or `dry_run` keys.
      Consumers should branch on `detail["mode"]`.
    - FINDING / CHANGED / WOULD_CHANGE: detail is a string (one line of formatter output).
    - ERROR: detail is a dict {"exit": int, "hint"?: str} or a string.
    - PLUGIN_AVAILABLE: event.tool is "mdformat"; detail is a dict
      {"plugin": str, "package": str, "version": str}. (The `tool` field
      lives on the Event itself, not inside `detail`.)
    - PLUGIN_MISSING: event.tool is "mdformat"; detail is a dict
      {"plugin": str, "package": str, "file": str, "reason": str}.
    - DELTA: detail is a dict {"resolved": int, "still_open": int, "new": int}.

    Full per-event schema lives in references/ndjson-schema.md.
    """

    AVAILABLE = "available"
    MISSING = "missing"
    INSTALLED = "installed"
    RECOMMEND = "recommend"
    VERDICT = "verdict"
    SELECTED = "selected"
    BUNDLED_CONFIG = "bundled-config"
    FINDING = "finding"
    CHANGED = "changed"
    WOULD_CHANGE = "would-change"
    CLEAN = "clean"
    ERROR = "error"
    PLUGIN_AVAILABLE = "plugin-available"
    PLUGIN_MISSING = "plugin-missing"
    DELTA = "delta"


@dataclass(frozen=True)
class Event:
    event: EventType
    tool: str
    detail: object
