"""Structural contracts for the release automation's identity."""

from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
_RELEASE_WORKFLOW = _REPO_ROOT / ".github" / "workflows" / "release-please.yml"


def _read() -> str:
    return _RELEASE_WORKFLOW.read_text(encoding="utf-8")


@pytest.mark.parametrize(
    "required_fragment",
    [
        "actions/create-github-app-token@bcd2ba49218906704ab6c1aa796996da409d3eb1",
        "client-id: ${{ secrets.OSS_RELEASE_BOT_CLIENT_ID }}",
        "private-key: ${{ secrets.OSS_RELEASE_BOT_PRIVATE_KEY }}",
        "token: ${{ steps.bot-token.outputs.token }}",
    ],
)
def test_release_please_acts_as_the_release_bot(required_fragment: str) -> None:
    # The identity audit alone cannot hold this: it pairs secrets with audit rows
    # and keeps the default token read-only, so dropping the mint step would still
    # pass it. These fragments pin the minted-App handoff the way the Dependabot
    # workflows' guards pin theirs.
    assert required_fragment in _read()


def test_release_please_never_runs_on_the_default_token() -> None:
    # The regression this rejects outright: handing `token: ${{ secrets.GITHUB_TOKEN }}`
    # back to release-please would pass the secret audit — GITHUB_TOKEN is legitimately
    # documented for the bundle jobs of this same workflow — while recreating the
    # release PR that reports no checks because default-token pushes trigger nothing.
    assert "token: ${{ secrets.GITHUB_TOKEN }}" not in _read()
