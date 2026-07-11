"""Guard the release wiring against drift.

`metadata.version` in each `SKILL.md` is the authoritative, consumer-facing version;
`.release-please-manifest.json` mirrors it as release-please's bump baseline, and
`release-please-config.json` `packages` decides which paths get released at all.
release-please keeps versions in sync on release, but a manual edit could silently
desync them — and a new skill forgotten in the config is silently never released.
These tests fail fast if the versions diverge or if either file gains or loses a skill.

Skills are resolved from *tracked* files (`git ls-files`), like
`tests/skills/test_distribution_hygiene.py`, so a local untracked scratch skill in the
working tree can't perturb the result — the wiring must match what actually ships.
"""

import json
import re
import subprocess
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
_MANIFEST = _REPO_ROOT / ".release-please-manifest.json"
_CONFIG = _REPO_ROOT / "release-please-config.json"

_VERSION = re.compile(r'^\s+version:\s*"([^"]+)"', flags=re.MULTILINE)


def _tracked_skill_paths() -> set[str]:
    """Return `skills/<name>` for every tracked `skills/<name>/SKILL.md`."""
    try:
        result = subprocess.run(
            ["git", "ls-files", "skills"],
            cwd=_REPO_ROOT,
            capture_output=True,
            text=True,
            check=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:  # pragma: no cover
        pytest.skip(f"git unavailable; cannot resolve tracked skills: {exc}")
    paths = set()
    for line in result.stdout.splitlines():
        parts = line.split("/")
        if len(parts) == 3 and parts[0] == "skills" and parts[2] == "SKILL.md":
            paths.add(f"skills/{parts[1]}")
    return paths


def _skill_version(skill_md: Path) -> str:
    match = _VERSION.search(skill_md.read_text(encoding="utf-8"))
    assert match, f"no metadata.version found in {skill_md}"
    return match.group(1)


def test_manifest_covers_exactly_the_skills() -> None:
    manifest = json.loads(_MANIFEST.read_text(encoding="utf-8"))
    assert set(manifest) == _tracked_skill_paths()


def test_config_packages_cover_exactly_the_skills() -> None:
    config = json.loads(_CONFIG.read_text(encoding="utf-8"))
    packages = config.get("packages")
    assert isinstance(packages, dict) and packages, (
        f"{_CONFIG.name} declares no `packages` mapping — release-please "
        "releases only the paths listed there, so every skill release hangs off it"
    )
    assert set(packages) == _tracked_skill_paths()


def test_manifest_versions_match_skill_md() -> None:
    manifest = json.loads(_MANIFEST.read_text(encoding="utf-8"))
    for path, version in manifest.items():
        skill_version = _skill_version(_REPO_ROOT / path / "SKILL.md")
        assert skill_version == version, (
            f"{path}: SKILL.md metadata.version {skill_version!r} != manifest {version!r}"
        )
