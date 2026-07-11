"""Pytest fixtures for the oss-repository-conventions skill self-tests.

The skill is documentation only (markdown): a router (SKILL.md) plus one
capability per domain under capabilities/ and shared references/. These tests
do not import any skill code; they validate the contracts unique to this
skill — the locked capability skeleton and the audit-output NDJSON schema.
Generic structure checks live in `tests/skills/test_structure_all.py`.
"""

from __future__ import annotations

from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[3]
_SKILL_ROOT = _REPO_ROOT / "skills" / "oss-repository-conventions"


@pytest.fixture(scope="session")
def skill_root() -> Path:
    """Absolute path to skills/oss-repository-conventions/."""
    return _SKILL_ROOT


@pytest.fixture(scope="session")
def capabilities_dir(skill_root: Path) -> Path:
    return skill_root / "capabilities"


@pytest.fixture(scope="session")
def references_dir(skill_root: Path) -> Path:
    return skill_root / "references"
