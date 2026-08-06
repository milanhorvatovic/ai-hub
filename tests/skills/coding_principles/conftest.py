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

# The language capabilities, declared rather than discovered from disk. The
# file-set contract asserts what each one must carry, so deriving the list from
# what is present would make that assertion vacuous — a capability that dropped
# a reference file would simply stop counting as a language. `review` and
# `comments` are workflow capabilities and are deliberately not in the list:
# both ship reference files of their own, and only this declaration keeps them
# out of the per-language contracts.
_LANGUAGE_CAPABILITIES = ("bash", "python", "rust", "typescript")

# Each language capability is `capability.md` plus a `references/` subdir
# holding the same seven supporting files (see the "File layout" section of
# SKILL.md).
_LANGUAGE_REFERENCE_FILES = frozenset(
    {
        "anti-patterns.md",
        "examples.md",
        "best-practices.md",
        "concurrency.md",
        "dependencies.md",
        "performance.md",
        "project-structure.md",
    }
)


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


@pytest.fixture(scope="session")
def language_capabilities() -> tuple[str, ...]:
    """The capabilities that carry per-language content, in name order."""
    return _LANGUAGE_CAPABILITIES


@pytest.fixture(scope="session")
def language_reference_files() -> frozenset[str]:
    """The seven reference files every language capability ships."""
    return _LANGUAGE_REFERENCE_FILES
