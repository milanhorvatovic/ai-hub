"""Pytest fixtures for the behavior-coach skill self-tests.

The skill is documentation only (markdown), so these tests do not import any
skill code — they validate the on-disk structure: frontmatter shape, semver
versioning, and cross-reference resolution between SKILL.md and references/.
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
