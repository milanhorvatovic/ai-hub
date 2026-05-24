"""Distribution-hygiene guard for the skills/ tree.

Everything under a skill directory ships to consumers via `npx skills` (and the
planned zip bundles), so a skill directory must contain only distributable skill
content — never repo-development artifacts (tests, tool configs, VCS dotfiles,
build/coverage artifacts). This test fails if any such file is *tracked* under
`skills/<name>/`, so the constraint can't silently regress.

It inspects tracked files (`git ls-files`) rather than the working tree: that is
exactly what a git-archive-based bundle ships, and it ignores local build caches
(e.g. `__pycache__`) that are gitignored and never distributed.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]

# Repo-development artifacts that are never skill content; shipping any of these
# would leak dev cruft to every consumer of the skill.
_DENY_BASENAMES = {
    "conftest.py",
    ".gitignore",
    ".gitattributes",
    ".editorconfig",
    ".pre-commit-config.yaml",
    "pyproject.toml",
    "setup.py",
    "setup.cfg",
    "tox.ini",
    ".coveragerc",
    ".coverage",
    "coverage.xml",
    ".DS_Store",
}
_DENY_NAME_PATTERNS = (
    re.compile(r"^test_.*\.py$"),
    re.compile(r".*_test\.py$"),
    re.compile(r"^requirements.*\.txt$"),
    re.compile(r".*\.py[co]$"),
    re.compile(r"^\.coverage\..+$"),  # parallel coverage data files (.coverage.host.pid)
    re.compile(r".*\.cover$"),  # *.cover / *.py.cover
)
_DENY_PATH_COMPONENTS = {
    "__pycache__",
    ".pytest_cache",
    ".ruff_cache",
    ".mypy_cache",
    ".hypothesis",
    "htmlcov",
    "cover",
    "tests",
    "test",
}


def _tracked_skill_files() -> list[str]:
    """Return repo-relative paths of every tracked file under `skills/`."""
    try:
        result = subprocess.run(
            ["git", "ls-files", "skills"],
            cwd=_REPO_ROOT,
            capture_output=True,
            text=True,
            check=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:  # pragma: no cover
        pytest.skip(f"git unavailable; cannot check distribution hygiene: {exc}")
    return [line for line in result.stdout.splitlines() if line]


def _is_non_distributable(rel_path: str) -> bool:
    parts = rel_path.split("/")
    if any(part in _DENY_PATH_COMPONENTS for part in parts):
        return True
    name = parts[-1]
    if name in _DENY_BASENAMES:
        return True
    return any(pattern.match(name) for pattern in _DENY_NAME_PATTERNS)


def test_skill_dirs_contain_only_distributable_content() -> None:
    """No repo-development artifact may be tracked under `skills/<name>/`.

    Skill directories are the distribution surface (npx skills / zip bundles);
    tests, tool configs, and VCS/build artifacts belong at the repo root or
    under `tests/`, never inside a shipped skill.
    """
    offenders = sorted(p for p in _tracked_skill_files() if _is_non_distributable(p))
    assert not offenders, (
        "non-distributable files tracked under skills/ — move them to the repo "
        f"root or tests/: {offenders}"
    )


@pytest.mark.parametrize(
    "rel_path",
    [
        "skills/x/conftest.py",
        "skills/x/test_thing.py",
        "skills/x/thing_test.py",
        "skills/x/.gitignore",
        "skills/x/pyproject.toml",
        "skills/x/requirements-dev.txt",
        "skills/x/module.pyc",
        "skills/x/.coverage",
        "skills/x/coverage.xml",
        "skills/x/.coverage.host.12345",
        "skills/x/results.cover",
        "skills/x/__pycache__/m.pyc",
        "skills/x/htmlcov/index.html",
        "skills/x/.hypothesis/examples/abc",
    ],
)
def test_predicate_flags_non_distributable(rel_path: str) -> None:
    assert _is_non_distributable(rel_path)


@pytest.mark.parametrize(
    "rel_path",
    [
        "skills/x/SKILL.md",
        "skills/x/capabilities/y/capability.md",
        "skills/x/references/z.md",
        "skills/x/assets/diagram.png",
        "skills/x/scripts/docs_steward/cli.py",
        "skills/x/scripts/md-audit.py",
    ],
)
def test_predicate_allows_distributable_content(rel_path: str) -> None:
    assert not _is_non_distributable(rel_path)
