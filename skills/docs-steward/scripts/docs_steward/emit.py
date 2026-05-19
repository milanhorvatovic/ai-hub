"""NDJSON event serialization.

Pure function: `serialize(event) -> str`. Uses `json.dumps` with stable key
ordering (event, tool, detail) for deterministic test assertions and easy
diffing. No newline appended — the CLI layer uses `print()` which adds it.
"""

from __future__ import annotations

import json

from .events import Event


def serialize(event: Event) -> str:
    payload = {
        "event": event.event.value,
        "tool": event.tool,
        "detail": event.detail,
    }
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
