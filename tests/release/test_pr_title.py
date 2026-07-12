"""Unit tests for the change-intent PR-title validator (`.github/scripts/validate_pr_title.py`).

Stdlib-only, in the same structural-test spirit as the skill self-tests: the module
lives outside the importable package tree (under `.github/scripts/`), so it is loaded
from its file path.
"""

import importlib.util
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SCRIPT = _REPO_ROOT / ".github" / "scripts" / "validate_pr_title.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("validate_pr_title", _SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


validator = _load_module()

SKILLS = {"coding-principles", "docs-steward", "git-toolkit", "oss-repository-conventions"}


@pytest.mark.parametrize(
    "title",
    [
        "feat(git-toolkit): add a release-notes capability",
        "fix(docs-steward): handle an empty findings stream",
        "docs(coding-principles): clarify the pruning tier",
        "feat(git-toolkit)!: drop the legacy branch-name flag",
        "build(release): configure release-please",
        "ci(repo): pin actions by sha",
        "chore(deps): bump the test runner",
        "refactor: simplify the router table",
    ],
)
def test_valid_titles(title: str) -> None:
    assert validator.validate(title, SKILLS) == []


@pytest.mark.parametrize(
    "title",
    [
        "Add a release-notes capability",  # no type prefix
        "feature(git-toolkit): add x",  # not a canonical type
        "feat(unknown-skill): add x",  # scope is neither a skill nor an area
        "feat(git-toolkit):missing space",  # missing space after colon
        "feat(git-toolkit): ",  # empty subject
        "feat(git-toolkit): add x.",  # trailing period
        "feat(git-toolkit): add x.  ",  # trailing period hidden by spaces
    ],
)
def test_invalid_titles(title: str) -> None:
    assert validator.validate(title, SKILLS) != []


def test_title_length_cap() -> None:
    long_title = "feat(git-toolkit): " + ("x" * 80)
    errors = validator.validate(long_title, SKILLS)
    assert any("cap is" in error for error in errors)


def test_skill_names_reads_real_repo() -> None:
    # Subset, not equality: adding a new skill must not break this test.
    # test_manifest_covers_exactly_the_skills enforces exact release wiring.
    assert SKILLS.issubset(validator.skill_names(_REPO_ROOT))
