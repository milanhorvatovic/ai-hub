"""Guard the skill-system manifest against drift.

`manifest.yaml` declares the skill fleet for skill-system-foundry tooling,
which only checks one direction (a manifest entry whose directory is missing).
The other direction — a skill or capability added to the tree but never
declared — would rot silently, so these tests pin the manifest to the tracked
tree both ways. Skills are resolved from *tracked* files (`git ls-files`),
like `tests/release/test_manifest_sync.py`, so untracked scratch skills can't
perturb the result.

The parser is line-based against the manifest's own layout (2-space skill
keys, 6-space `- capability` items) — the suite is stdlib-only, no PyYAML.
"""

import re
import subprocess
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
_MANIFEST = _REPO_ROOT / "manifest.yaml"

_SKILL_KEY = re.compile(r"^  ([a-z0-9-]+):\s*$")
_CAPABILITY_ITEM = re.compile(r"^      - ([a-z0-9-]+)\s*$")
_CANONICAL_LINE = re.compile(r"^\s+canonical:\s*(\S+)")


def _tracked_files() -> list[str]:
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
    return result.stdout.splitlines()


def _tree_skills() -> dict[str, set[str]]:
    """Tracked `skills/<name>` -> set of tracked capability names."""
    skills: dict[str, set[str]] = {}
    for line in _tracked_files():
        parts = line.split("/")
        if len(parts) == 3 and parts[2] == "SKILL.md":
            skills.setdefault(parts[1], set())
        if len(parts) == 5 and parts[2] == "capabilities" and parts[4] == "capability.md":
            skills.setdefault(parts[1], set()).add(parts[3])
    return skills


def _manifest_skills() -> dict[str, set[str]]:
    """Manifest `skills:` entries -> declared capability names."""
    skills: dict[str, set[str]] = {}
    in_skills = False
    current: str | None = None
    for line in _MANIFEST.read_text(encoding="utf-8").splitlines():
        if line.startswith("skills:"):
            in_skills = True
            continue
        if line and not line[0].isspace() and not line.startswith("#"):
            in_skills = False
        if not in_skills:
            continue
        if m := _SKILL_KEY.match(line):
            current = m.group(1)
            skills[current] = set()
        elif current and (m := _CAPABILITY_ITEM.match(line)):
            skills[current].add(m.group(1))
    return skills


def test_manifest_declares_exactly_the_tracked_skills() -> None:
    manifest, tree = _manifest_skills(), _tree_skills()
    assert manifest.keys() == tree.keys(), (
        f"manifest/tree skill drift: manifest-only={sorted(manifest.keys() - tree.keys())}, "
        f"tree-only={sorted(tree.keys() - manifest.keys())}"
    )


def test_manifest_capabilities_match_the_tracked_tree() -> None:
    manifest, tree = _manifest_skills(), _tree_skills()
    drift = [
        f"{skill}: manifest-only={sorted(caps - tree.get(skill, set()))}, "
        f"tree-only={sorted(tree.get(skill, set()) - caps)}"
        for skill, caps in sorted(manifest.items())
        if caps != tree.get(skill, set())
    ]
    assert not drift, "manifest/tree capability drift:\n" + "\n".join(drift)


def test_manifest_canonical_paths_resolve() -> None:
    paths = [
        m.group(1)
        for line in _MANIFEST.read_text(encoding="utf-8").splitlines()
        if (m := _CANONICAL_LINE.match(line))
    ]
    assert paths, "manifest declares no canonical paths"
    missing = [p for p in paths if not (_REPO_ROOT / p).is_file()]
    assert not missing, f"manifest canonical paths that do not resolve: {missing}"
