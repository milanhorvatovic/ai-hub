"""docs-steward — orchestrates markdown formatters with a uniform NDJSON contract.

Public API is exposed for embedding; the canonical entry points are the six
shim scripts under `scripts/` — `probe.py`, `recommend-tools.py`, `md-audit.py`,
`md-format.py`, `md-fix.py`, and `md-audit-frontmatter.py` — each of which
delegates to `docs_steward.cli.main`.
"""

from .events import Event, EventType
from .modes import Mode
from .tools import Tool

__all__ = ["Event", "EventType", "Mode", "Tool"]
