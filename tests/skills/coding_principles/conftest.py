"""Pytest fixtures for the coding-principles skill self-tests.

The skill is documentation only (markdown), so these tests do not import any
skill code — they validate the contracts unique to this skill: the advertised
mantra/principle counts, capability name slugs, the per-language file set,
and the pointer↔example coupling. Generic structure checks live in
`tests/skills/test_structure_all.py`.
"""

from __future__ import annotations

from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[3]
_SKILL_ROOT = _REPO_ROOT / "skills" / "coding-principles"


@pytest.fixture(scope="session")
def skill_root() -> Path:
    """Absolute path to skills/coding-principles/."""
    return _SKILL_ROOT


@pytest.fixture(scope="session")
def skill_md(skill_root: Path) -> Path:
    return skill_root / "SKILL.md"


@pytest.fixture(scope="session")
def capabilities_dir(skill_root: Path) -> Path:
    return skill_root / "capabilities"


@pytest.fixture(scope="session")
def references_dir(skill_root: Path) -> Path:
    return skill_root / "references"
