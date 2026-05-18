"""docs-steward — orchestrates markdown formatters with a uniform NDJSON contract.

Public API is exposed for embedding; the canonical entry points are the four
shim scripts under `scripts/` (probe.py, audit.py, format.py, recommend-tools.py)
which delegate to `docs_steward.cli.main`.
"""

from .events import Event, EventType
from .modes import Mode
from .tools import Tool

__all__ = ["Event", "EventType", "Mode", "Tool"]
