"""Tests for ``gen_changelog``: pure-function units + an end-to-end temp-repo run.

The script under test lives under ``.github/scripts/`` (sibling of
``build_bundles.py``), so we add that directory to ``sys.path`` before importing
it as a module — mirroring how the other release tests reach their scripts.
"""

from __future__ import annotations

import os
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SCRIPTS = _REPO_ROOT / ".github" / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

import gen_changelog  # noqa: E402, I001 — sys.path adjustment must precede


# --------------------------------------------------------------------------- #
# parse_conventional
# --------------------------------------------------------------------------- #


def test_parse_conventional_with_scope() -> None:
    commit = gen_changelog.parse_conventional(
        "feat(docs-steward): add YAML frontmatter audit"
    )
    assert commit is not None
    assert commit.type == "feat"
    assert commit.scope == "docs-steward"
    assert commit.breaking is False
    assert commit.desc == "add YAML frontmatter audit"


def test_parse_conventional_without_scope() -> None:
    commit = gen_changelog.parse_conventional("fix: handle empty input")
    assert commit is not None
    assert commit.type == "fix"
    assert commit.scope is None
    assert commit.breaking is False


def test_parse_conventional_breaking_via_bang() -> None:
    commit = gen_changelog.parse_conventional("feat!: rework public API")
    assert commit is not None
    assert commit.breaking is True
    assert commit.scope is None


def test_parse_conventional_non_conventional_returns_none() -> None:
    assert gen_changelog.parse_conventional("Add coding-principles skill") is None
    assert gen_changelog.parse_conventional("Merge branch 'foo'") is None
    assert gen_changelog.parse_conventional("") is None


# --------------------------------------------------------------------------- #
# group_commits
# --------------------------------------------------------------------------- #


def _commit(type_: str, desc: str, *, breaking: bool = False) -> gen_changelog.Commit:
    return gen_changelog.Commit(
        sha="0" * 7, type=type_, scope=None, breaking=breaking, desc=desc
    )


def test_group_commits_orders_categories_and_drops_silent_types() -> None:
    commits = [
        _commit("feat", "added thing"),
        _commit("chore", "internal noise"),
        _commit("fix", "fixed thing"),
        _commit("test", "more noise"),
        _commit("perf", "perf tweak"),
        _commit("refactor", "rename"),
    ]
    groups = gen_changelog.group_commits(commits)
    assert list(groups.keys()) == ["Added", "Changed", "Fixed"]
    assert [c.desc for c in groups["Added"]] == ["added thing"]
    assert [c.desc for c in groups["Changed"]] == ["perf tweak", "rename"]
    assert [c.desc for c in groups["Fixed"]] == ["fixed thing"]


def test_group_commits_breaking_non_mapped_type_lands_in_changed() -> None:
    groups = gen_changelog.group_commits([_commit("chore", "big rework", breaking=True)])
    assert "Changed" in groups
    assert groups["Changed"][0].breaking is True


# --------------------------------------------------------------------------- #
# format_skill_section
# --------------------------------------------------------------------------- #


def test_format_skill_section_no_changes_is_empty() -> None:
    assert gen_changelog.format_skill_section("docs-steward", "1.1.0", {}) == ""


def test_format_skill_section_renders_categories_and_breaking_marker() -> None:
    groups = {
        "Added": [_commit("feat", "yaml audit")],
        "Fixed": [_commit("fix", "edge case", breaking=True)],
    }
    out = gen_changelog.format_skill_section("docs-steward", "1.2.0", groups)
    assert "### docs-steward 1.2.0" in out
    assert "#### Added" in out
    assert "- yaml audit" in out
    assert "#### Fixed" in out
    assert "- **BREAKING:** edge case" in out


# --------------------------------------------------------------------------- #
# format_calver_section
# --------------------------------------------------------------------------- #


def test_format_calver_section_skips_empty_skills() -> None:
    sections = [
        ("docs-steward", "1.1.0", {"Added": [_commit("feat", "x")]}),
        ("git-toolkit", "1.0.0", {}),  # no changes — entirely omitted
    ]
    out = gen_changelog.format_calver_section("v2026.05.1", "2026-05-26", sections)
    assert out.startswith("## v2026.05.1 — 2026-05-26")
    assert "### docs-steward 1.1.0" in out
    assert "### git-toolkit" not in out


def test_format_calver_section_all_empty_emits_placeholder() -> None:
    sections = [("docs-steward", "1.1.0", {})]
    out = gen_changelog.format_calver_section("v2026.05.1", "2026-05-26", sections)
    assert "## v2026.05.1 — 2026-05-26" in out
    assert "_No user-visible changes._" in out


# --------------------------------------------------------------------------- #
# rewrite_changelog
# --------------------------------------------------------------------------- #


def test_rewrite_changelog_replaces_existing_calver_section() -> None:
    existing = textwrap.dedent(
        """\
        # Changelog

        ## v2026.05.0 — 2026-05-24

        old content

        ## v2026.04.0 — 2026-04-01

        prior section
        """
    )
    new_section = "## v2026.05.0 — 2026-05-26\n\nnew content\n"
    out = gen_changelog.rewrite_changelog(existing, new_section, "v2026.05.0")
    assert "old content" not in out
    assert "new content" in out
    assert "prior section" in out  # untouched


def test_rewrite_changelog_prepends_new_section_after_intro() -> None:
    existing = textwrap.dedent(
        """\
        # Changelog

        Intro paragraph.

        ## v2026.05.0 — 2026-05-24

        first section
        """
    )
    new_section = "## v2026.05.1 — 2026-05-26\n\nnext section\n"
    out = gen_changelog.rewrite_changelog(existing, new_section, "v2026.05.1")
    new_pos = out.index("## v2026.05.1")
    old_pos = out.index("## v2026.05.0")
    assert new_pos < old_pos
    assert "# Changelog" in out
    assert "Intro paragraph." in out
    assert "first section" in out


def test_rewrite_changelog_is_idempotent() -> None:
    existing = "# Changelog\n\n## v2026.05.1 — 2026-05-26\n\noriginal\n"
    new = "## v2026.05.1 — 2026-05-26\n\noriginal\n"
    first = gen_changelog.rewrite_changelog(existing, new, "v2026.05.1")
    second = gen_changelog.rewrite_changelog(first, new, "v2026.05.1")
    assert first == second


# --------------------------------------------------------------------------- #
# End-to-end: temp git repo with a manifest, tags, and commits
# --------------------------------------------------------------------------- #


def _git(cwd: Path, *args: str) -> None:
    """Run git hermetically (no global config / signing) and surface stderr on failure."""
    env = {
        **os.environ,
        "GIT_CONFIG_GLOBAL": "/dev/null",
        "GIT_CONFIG_SYSTEM": "/dev/null",
        "GIT_TERMINAL_PROMPT": "0",
    }
    result = subprocess.run(
        ["git", *args], cwd=cwd, capture_output=True, text=True, env=env
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"git {' '.join(args)} failed (exit {result.returncode}):\n{result.stderr}"
        )


@pytest.fixture
def fake_repo(tmp_path: Path) -> Path:
    _git(tmp_path, "init", "-q", "-b", "main")
    _git(tmp_path, "config", "user.email", "test@example.com")
    _git(tmp_path, "config", "user.name", "Test")

    skill_dir = tmp_path / "skills" / "alpha"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        '---\nname: alpha\nmetadata:\n  version: "1.0.0"\n---\n',
        encoding="utf-8",
    )
    (tmp_path / ".release-please-manifest.json").write_text(
        '{"skills/alpha": "1.1.0"}\n', encoding="utf-8"
    )
    (tmp_path / "CHANGELOG.md").write_text("# Changelog\n\n", encoding="utf-8")
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-q", "-m", "feat(alpha): initial release")
    _git(tmp_path, "tag", "alpha-v1.0.0")
    return tmp_path


def test_end_to_end_writes_changelog_with_post_tag_commits(fake_repo: Path) -> None:
    # Add commits that should land in the next release.
    (fake_repo / "skills" / "alpha" / "feature.md").write_text("hi", encoding="utf-8")
    _git(fake_repo, "add", "-A")
    _git(fake_repo, "commit", "-q", "-m", "feat(alpha): add greeting")

    (fake_repo / "skills" / "alpha" / "patch.md").write_text("p", encoding="utf-8")
    _git(fake_repo, "add", "-A")
    _git(fake_repo, "commit", "-q", "-m", "fix(alpha): clean up")

    rc = gen_changelog.main(
        [
            "--repo-root",
            str(fake_repo),
            "--calver",
            "v2026.05.1",
            "--date",
            "2026-05-26",
        ]
    )
    assert rc == 0

    content = (fake_repo / "CHANGELOG.md").read_text(encoding="utf-8")
    assert "## v2026.05.1 — 2026-05-26" in content
    assert "### alpha 1.1.0" in content
    assert "#### Added" in content
    assert "- add greeting" in content
    assert "#### Fixed" in content
    assert "- clean up" in content
    # The pre-tag commit message must not leak into the new section.
    assert "initial release" not in content


def test_end_to_end_no_post_tag_changes_emits_placeholder(fake_repo: Path) -> None:
    # No commits added since the tag; the section should still appear but with
    # a no-changes placeholder so we never write a malformed section.
    rc = gen_changelog.main(
        [
            "--repo-root",
            str(fake_repo),
            "--calver",
            "v2026.05.1",
            "--date",
            "2026-05-26",
        ]
    )
    assert rc == 0
    content = (fake_repo / "CHANGELOG.md").read_text(encoding="utf-8")
    assert "## v2026.05.1 — 2026-05-26" in content
    assert "_No user-visible changes._" in content
