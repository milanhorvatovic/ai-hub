"""Guard the two version sources against drift.

`metadata.version` in each `SKILL.md` is the authoritative, consumer-facing version;
`.release-please-manifest.json` mirrors it as release-please's bump baseline. release-please
keeps them in sync on release, but a manual edit to one could silently desync the other —
this test fails fast if they diverge, and if the manifest gains or loses a skill.
"""

import json
import re
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_MANIFEST = _REPO_ROOT / ".release-please-manifest.json"
_SKILLS_DIR = _REPO_ROOT / "skills"

_VERSION = re.compile(r'^\s+version:\s*"([^"]+)"', flags=re.MULTILINE)


def _skill_version(skill_md: Path) -> str:
    match = _VERSION.search(skill_md.read_text(encoding="utf-8"))
    assert match, f"no metadata.version found in {skill_md}"
    return match.group(1)


def test_manifest_covers_exactly_the_skills() -> None:
    manifest = json.loads(_MANIFEST.read_text(encoding="utf-8"))
    manifest_paths = set(manifest)
    skill_paths = {
        f"skills/{p.name}" for p in _SKILLS_DIR.iterdir() if (p / "SKILL.md").is_file()
    }
    assert manifest_paths == skill_paths


def test_manifest_versions_match_skill_md() -> None:
    manifest = json.loads(_MANIFEST.read_text(encoding="utf-8"))
    for path, version in manifest.items():
        skill_version = _skill_version(_REPO_ROOT / path / "SKILL.md")
        assert skill_version == version, (
            f"{path}: SKILL.md metadata.version {skill_version!r} != manifest {version!r}"
        )
