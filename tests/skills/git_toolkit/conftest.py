"""Pytest fixtures for the git-toolkit skill self-tests.

The skill is documentation only (markdown + JSON Schema), so these tests do
not import any skill code — they validate the contracts unique to this skill:
the review-output NDJSON schema and the untrusted-content guard wiring.
Generic structure checks live in `tests/skills/test_structure_all.py`.
"""

from __future__ import annotations

from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[3]
_SKILL_ROOT = _REPO_ROOT / "skills" / "git-toolkit"


@pytest.fixture(scope="session")
def skill_root() -> Path:
    """Absolute path to skills/git-toolkit/."""
    return _SKILL_ROOT


@pytest.fixture(scope="session")
def capabilities_dir(skill_root: Path) -> Path:
    return skill_root / "capabilities"


@pytest.fixture(scope="session")
def references_dir(skill_root: Path) -> Path:
    return skill_root / "references"
