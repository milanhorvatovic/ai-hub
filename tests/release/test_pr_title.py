"""Unit tests for the change-intent PR-title validator (`.github/scripts/validate_pr_title.py`).

Stdlib-only, in the same structural-test spirit as the skill self-tests: the module
lives outside the importable package tree (under `.github/scripts/`), so it is loaded
from its file path.
"""

import importlib.util
import os
import subprocess
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SCRIPT = _REPO_ROOT / ".github" / "scripts" / "validate_pr_title.py"
_WORKFLOW = _REPO_ROOT / ".github" / "workflows" / "change-intent.yml"


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


# --- bot length exemption -----------------------------------------------------------

# The grouped Dependabot title from the triage that motivated the exemption: a valid
# Conventional Commit whose only fault is length (83 chars; the cap is 72). Dependabot
# appends the `in the <group> group across N director...` suffix and no dependabot.yaml
# setting can shorten it.
BOT_LONG_TITLE = "build(deps): bump pytest from 9.0.3 to 9.1.1 in the python group across 1 directory"


def test_bot_waiver_passes_a_long_but_valid_title() -> None:
    assert len(BOT_LONG_TITLE) > validator.TITLE_MAX
    assert validator.validate(BOT_LONG_TITLE, SKILLS, waive_length=True) == []


def test_the_same_long_title_fails_for_a_human() -> None:
    errors = validator.validate(BOT_LONG_TITLE, SKILLS)
    assert any("cap is" in error for error in errors)


@pytest.mark.parametrize(
    "title",
    [
        # A bad type is still rejected under the waiver — and it is over-length too,
        # proving the waiver is active yet the structural check still fires.
        "feature(deps): bump pytest from 9.0.3 to 9.1.1 in the python group across 1 dir",
        # A scope that is neither a skill nor a repo area is still rejected.
        "build(unknown): bump pytest from 9.0.3 to 9.1.1 in the python group across 1 dir",
    ],
)
def test_bot_waiver_is_length_only(title: str) -> None:
    assert len(title) > validator.TITLE_MAX  # would fail on length if the waiver leaked
    assert validator.validate(title, SKILLS, waive_length=True) != []


@pytest.mark.parametrize(
    "login,is_bot",
    [
        ("dependabot[bot]", True),
        ("github-actions[bot]", True),
        # A custom App, of the kind docs/adr/0002-automation-identity.md moves the
        # release path onto. The waiver is by shape, so an App that does not exist yet
        # is already covered and there is no list to extend when one is created.
        ("ai-hub-automation[bot]", True),
        ("renovate-bot", True),
        ("milanhorvatovic", False),
        ("botanist", False),  # a bare "bot" substring is not a bot marker
    ],
)
def test_is_bot_login(login: str, is_bot: bool) -> None:
    assert validator.is_bot_login(login) is is_bot


def test_change_intent_workflow_passes_author_to_the_title_validator() -> None:
    # The validator waives the cap by author, so the pr-title step must feed it
    # PR_AUTHOR — via env, the same untrusted-input discipline as PR_TITLE. Assert the
    # two are wired together in that step: the commit-style job also sets PR_AUTHOR, so
    # a bare substring check would pass even if the title step never got it. PR_TITLE is
    # set only by the pr-title step, so PR_AUTHOR on the next line pins it to that step.
    lines = _WORKFLOW.read_text(encoding="utf-8").splitlines()
    title_env = [i for i, line in enumerate(lines) if "PR_TITLE: ${{ github.event.pull_request.title }}" in line]
    assert title_env, "the pr-title step must set PR_TITLE from the event payload"
    assert any(
        i + 1 < len(lines) and "PR_AUTHOR: ${{ github.event.pull_request.user.login }}" in lines[i + 1]
        for i in title_env
    ), "the pr-title step must set PR_AUTHOR right after PR_TITLE"
    assert "validate_pr_title.py" in _WORKFLOW.read_text(encoding="utf-8")


# --- CLI: main() reads the author from the env end to end ----------------------------


def _run_validator(title: str, author: str = "") -> subprocess.CompletedProcess:
    # main() reads PR_TITLE and PR_AUTHOR from the environment — never argv — because
    # both are attacker-controllable on fork PRs. Drive it exactly as the workflow does.
    env = {**os.environ, "PR_TITLE": title, "PR_AUTHOR": author}
    return subprocess.run([sys.executable, str(_SCRIPT)], env=env, capture_output=True, text=True)


def test_cli_bot_author_waives_the_length_cap() -> None:
    passed = _run_validator(BOT_LONG_TITLE, "dependabot[bot]")
    assert passed.returncode == 0
    assert "waived" in passed.stdout
    # The same over-length title from a human still fails on length...
    human = _run_validator(BOT_LONG_TITLE, "milanhorvatovic")
    assert human.returncode == 1
    # ...and with no author at all, the gate fails closed rather than waiving.
    no_author = _run_validator(BOT_LONG_TITLE)
    assert no_author.returncode == 1


def test_cli_bot_waiver_is_length_only() -> None:
    # A bot title that is malformed, not merely long, is still rejected.
    result = _run_validator("feature(deps): bump pytest from 9.0.3 to 9.1.1 in the python group across 1 dir", "dependabot[bot]")
    assert result.returncode == 1


def test_skill_names_reads_real_repo() -> None:
    # Subset, not equality: adding a new skill must not break this test.
    # test_manifest_covers_exactly_the_skills enforces exact release wiring.
    assert SKILLS.issubset(validator.skill_names(_REPO_ROOT))
