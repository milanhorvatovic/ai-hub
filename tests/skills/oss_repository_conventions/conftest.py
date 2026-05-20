"""Pytest fixtures for the oss-repository-conventions skill self-tests.

The skill is documentation only (markdown) and, unlike the router skills in
this repo, ships no `capabilities/` directory — it is a single-file scanner
with one reference catalog. These tests do not import any skill code; they
validate the on-disk structure: frontmatter shape, semver versioning, and
cross-reference resolution between SKILL.md and references/.
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
def skill_md(skill_root: Path) -> Path:
    return skill_root / "SKILL.md"


@pytest.fixture(scope="session")
def references_dir(skill_root: Path) -> Path:
    return skill_root / "references"
