"""Unit tests for the skill-bundle builder (`.github/scripts/build_bundles.py`).

Stdlib-only, in the same structural-test spirit as the other release scripts: the
module lives outside the importable package tree (under `.github/scripts/`), so it
is loaded from its file path. The tests build from the real repository at `HEAD`,
which is exactly what the release workflow archives.
"""

from __future__ import annotations

import hashlib
import importlib.util
import subprocess
import zipfile
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SCRIPT = _REPO_ROOT / ".github" / "scripts" / "build_bundles.py"


def _git_unavailable() -> bool:
    """True when git or a real worktree is missing — the build tests can't run then."""
    try:
        subprocess.run(
            ["git", "rev-parse", "--is-inside-work-tree"],
            cwd=_REPO_ROOT,
            capture_output=True,
            check=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return True
    return False


# Like tests/release/test_manifest_sync.py: skip rather than hard-fail where git is absent
# (sdists, minimal images), since the builder shells out to git against the checkout.
pytestmark = pytest.mark.skipif(
    _git_unavailable(), reason="git/worktree unavailable; build bundles need a real checkout"
)


def _load_module():
    spec = importlib.util.spec_from_file_location("build_bundles", _SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


builder = _load_module()

# A skill that exists at HEAD; any tracked skill would do.
_SKILL = "git-toolkit"


def test_bundle_is_named_for_skill_and_version(tmp_path: Path) -> None:
    version = builder.skill_version(_REPO_ROOT, "HEAD", _SKILL)
    bundle = builder.build_skill_bundle(_REPO_ROOT, "HEAD", _SKILL, tmp_path)
    assert bundle.name == f"{_SKILL}-{version}.zip"
    assert bundle.parent == tmp_path


def test_bundle_contains_skill_content_under_top_dir(tmp_path: Path) -> None:
    bundle = builder.build_skill_bundle(_REPO_ROOT, "HEAD", _SKILL, tmp_path)
    with zipfile.ZipFile(bundle) as archive:
        names = set(archive.namelist())
    # SKILL.md is rehomed under the bundle's top-level <skill>/ directory.
    assert f"{_SKILL}/SKILL.md" in names
    # Every entry is namespaced under the skill directory — no bare or stray paths.
    assert all(name.startswith(f"{_SKILL}/") for name in names)
    # The `skills/` repo prefix is stripped, not carried into the bundle.
    assert not any(name.startswith("skills/") for name in names)


def test_bundle_injects_license(tmp_path: Path) -> None:
    bundle = builder.build_skill_bundle(_REPO_ROOT, "HEAD", _SKILL, tmp_path)
    with zipfile.ZipFile(bundle) as archive:
        license_text = archive.read(f"{_SKILL}/LICENSE").decode("utf-8")
    assert "MIT License" in license_text


def test_bundle_excludes_repo_development_cruft(tmp_path: Path) -> None:
    bundle = builder.build_skill_bundle(_REPO_ROOT, "HEAD", _SKILL, tmp_path)
    with zipfile.ZipFile(bundle) as archive:
        names = archive.namelist()
    # The skill subtree ships only distributable content — no tests, configs, or VCS dotfiles.
    for stray in ("conftest.py", "pyproject.toml", ".gitignore", "__pycache__"):
        assert not any(stray in name for name in names), f"{stray!r} leaked into the bundle"


def test_bundle_is_byte_reproducible(tmp_path: Path) -> None:
    first = builder.build_skill_bundle(_REPO_ROOT, "HEAD", _SKILL, tmp_path / "a")
    second = builder.build_skill_bundle(_REPO_ROOT, "HEAD", _SKILL, tmp_path / "b")
    assert first.read_bytes() == second.read_bytes()
    assert (
        hashlib.sha256(first.read_bytes()).hexdigest()
        == hashlib.sha256(second.read_bytes()).hexdigest()
    )


def test_sha256sums_is_coreutils_format(tmp_path: Path) -> None:
    bundle = builder.build_skill_bundle(_REPO_ROOT, "HEAD", _SKILL, tmp_path)
    sums = builder.write_sha256sums([bundle], tmp_path / "SHA256SUMS")
    line = sums.read_text(encoding="utf-8").splitlines()[0]
    digest, _, name = line.partition("  ")  # two spaces = sha256sum text-mode separator
    assert name == bundle.name
    assert digest == hashlib.sha256(bundle.read_bytes()).hexdigest()
    assert len(digest) == 64


def test_sha256sums_lists_every_bundle_sorted(tmp_path: Path) -> None:
    skills = builder._resolve_skills(_REPO_ROOT, "HEAD", [])
    bundles = [builder.build_skill_bundle(_REPO_ROOT, "HEAD", s, tmp_path) for s in skills]
    sums = builder.write_sha256sums(bundles, tmp_path / "SHA256SUMS")
    listed = [line.split("  ", 1)[1] for line in sums.read_text(encoding="utf-8").splitlines()]
    assert listed == sorted(b.name for b in bundles)


def test_resolve_skills_defaults_to_all_tracked_skills() -> None:
    resolved = builder._resolve_skills(_REPO_ROOT, "HEAD", [])
    assert {"coding-principles", "docs-steward", "git-toolkit", "oss-repository-conventions"} <= set(
        resolved
    )


def test_skill_version_matches_manifest() -> None:
    # The builder's version read must agree with the release manifest's source of truth.
    import json

    manifest = json.loads((_REPO_ROOT / ".release-please-manifest.json").read_text(encoding="utf-8"))
    expected = manifest[f"skills/{_SKILL}"]
    assert builder.skill_version(_REPO_ROOT, "HEAD", _SKILL) == expected


def test_missing_skill_raises(tmp_path: Path) -> None:
    # A non-existent skill makes `git show <ref>:skills/<name>/SKILL.md` exit non-zero,
    # which surfaces as CalledProcessError — assert that exact mode, not "any exception".
    with pytest.raises(subprocess.CalledProcessError):
        builder.build_skill_bundle(_REPO_ROOT, "HEAD", "no-such-skill", tmp_path)
