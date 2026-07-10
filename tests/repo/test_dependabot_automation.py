"""Structural contracts for the repository's Dependabot autonomy policy."""

import re
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
_DEPENDABOT_CONFIG = _REPO_ROOT / ".github" / "dependabot.yaml"
_AUTO_MERGE_WORKFLOW = _REPO_ROOT / ".github" / "workflows" / "dependabot-auto-merge.yaml"
_RECONCILER_WORKFLOW = _REPO_ROOT / ".github" / "workflows" / "dependabot-reconciler.yaml"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_dependabot_groups_exclude_major_updates() -> None:
    config = _read(_DEPENDABOT_CONFIG)

    update_type_groups = re.findall(
        r"update-types:\s*\[\s*[\"']minor[\"']\s*,\s*[\"']patch[\"']\s*\]",
        config,
    )
    assert len(update_type_groups) == 2
    assert "actions/attest-build-provenance" in config
    assert "googleapis/release-please-action" in config
    assert "dependency-name: dependabot/fetch-metadata" in config


@pytest.mark.parametrize(
    "required_fragment",
    [
        "github.event.pull_request.user.login == 'dependabot[bot]' || github.event.pull_request.user.login == 'app/dependabot'",
        "github.event.pull_request.head.repo.full_name == github.repository",
        "pull_request:",
        "github.event.action != 'labeled'",
        "dependabot/fetch-metadata@25dd0e34f4fe68f24cc83900b1fe3fe149efef98",
        "steps.metadata.outputs.update-type != 'version-update:semver-major'",
        "!contains(steps.metadata.outputs.dependency-names, 'actions/attest-build-provenance')",
        "!contains(steps.metadata.outputs.dependency-names, 'googleapis/release-please-action')",
        "vars.DEPENDABOT_AUTOMERGE_ENABLED == 'true'",
        "secrets.CODEOWNER_APPROVER_TOKEN",
        "gh pr review --approve",
        "gh pr merge --auto --squash",
        "trust-boundary",
        "security-review-required",
    ],
)
def test_auto_merge_workflow_keeps_policy_guard(required_fragment: str) -> None:
    assert required_fragment in _read(_AUTO_MERGE_WORKFLOW)


def test_workflow_never_checks_out_pr_code() -> None:
    workflow = _read(_AUTO_MERGE_WORKFLOW)

    assert "pull_request:" in workflow
    assert "pull_request_target:" not in workflow
    assert "actions/checkout@" not in workflow


@pytest.mark.parametrize(
    "required_fragment",
    [
        "workflow_run:",
        "schedule:",
        'cron: "*/30 * * * *"',
        "AUTOMERGE_ENABLED: ${{ vars.DEPENDABOT_AUTOMERGE_ENABLED }}",
        "GH_TOKEN: ${{ secrets.CODEOWNER_APPROVER_TOKEN }}",
        "GH_REPO: ${{ github.repository }}",
        "gh pr list --search 'author:dependabot[bot]'",
        "gh pr list --search 'author:app/dependabot'",
        "gh pr update-branch",
        "gh pr merge --auto --squash",
        "trust-boundary",
        "security-review-required",
    ],
)
def test_reconciler_keeps_recovery_guard(required_fragment: str) -> None:
    assert required_fragment in _read(_RECONCILER_WORKFLOW)
