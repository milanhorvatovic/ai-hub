"""Pytest fixtures for the behavior-coach skill self-tests.

The skill is documentation only (markdown), so these tests do not import any
skill code — they validate the contracts unique to this skill: the six-stage
pipeline, the prompt-level-only scope boundary, and the honest-limits
requirement on produced skills. Generic structure checks live in
`tests/skills/test_structure_all.py`.
"""

from __future__ import annotations

from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[3]
_SKILL_ROOT = _REPO_ROOT / "skills" / "behavior-coach"


@pytest.fixture(scope="session")
def skill_root() -> Path:
    """Absolute path to skills/behavior-coach/."""
    return _SKILL_ROOT


@pytest.fixture(scope="session")
def skill_md(skill_root: Path) -> Path:
    return skill_root / "SKILL.md"


@pytest.fixture(scope="session")
def references_dir(skill_root: Path) -> Path:
    return skill_root / "references"
