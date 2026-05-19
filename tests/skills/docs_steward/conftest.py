"""Add the docs-steward runtime package to sys.path for test imports."""

from __future__ import annotations

import sys
from pathlib import Path

_SKILL_SCRIPTS = Path(__file__).resolve().parents[3] / "skills" / "docs-steward" / "scripts"
if str(_SKILL_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SKILL_SCRIPTS))
