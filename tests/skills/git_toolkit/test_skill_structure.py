"""Structural tests for skills/git-toolkit/SKILL.md.

Validates the router file's frontmatter, version, capability table, and that
every capability referenced in the router actually exists on disk (and vice
versa — no orphan capabilities living in capabilities/ that the router does
not advertise).
"""

from __future__ import annotations

import re
from pathlib import Path


def _parse_frontmatter(md_path: Path) -> dict[str, str]:
    """Parse a leading YAML frontmatter block into a flat dict.

    Hand-rolled because the skill's tests run with Python stdlib only — no
    PyYAML dependency. Handles flat key: value pairs and the multi-line `>`
    folded string used in skill descriptions.
    """
    text = md_path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        raise AssertionError(f"{md_path} missing leading frontmatter")
    end = text.find("\n---\n", 4)
    if end == -1:
        raise AssertionError(f"{md_path} frontmatter not terminated")
    body = text[4:end]

    result: dict[str, str] = {}
    current_key: str | None = None
    current_lines: list[str] = []
    for raw in body.splitlines():
        if raw.startswith("  ") and current_key is not None:
            current_lines.append(raw.strip())
            continue
        if current_key is not None:
            result[current_key] = (
                " ".join(current_lines).strip()
                if current_lines
                else result[current_key]
            )
            current_key = None
            current_lines = []
        m = re.match(r"^([a-zA-Z_-]+):\s*(.*)$", raw)
        if not m:
            continue
        key, value = m.group(1), m.group(2).strip()
        if value in {">", "|"}:
            current_key = key
            current_lines = []
            result[key] = ""
        else:
            result[key] = value
    if current_key is not None:
        result[current_key] = " ".join(current_lines).strip()
    return result


def test_skill_md_exists(skill_md: Path) -> None:
    assert skill_md.is_file(), f"{skill_md} not found"


def test_skill_md_has_frontmatter(skill_md: Path) -> None:
    fm = _parse_frontmatter(skill_md)
    assert "name" in fm, "frontmatter missing required `name`"
    assert "description" in fm, "frontmatter missing required `description`"
    assert fm["name"] == "git-toolkit"


def test_skill_version_is_semver(skill_md: Path) -> None:
    text = skill_md.read_text(encoding="utf-8")
    m = re.search(r'^\s+version:\s*"([^"]+)"', text, flags=re.MULTILINE)
    assert m, "no version: key found in metadata"
    version = m.group(1)
    semver = re.fullmatch(r"\d+\.\d+\.\d+(-[0-9A-Za-z.-]+)?", version)
    assert semver, f"version `{version}` is not semver"


def test_capability_table_lists_existing_paths(
    skill_md: Path, capabilities_dir: Path
) -> None:
    """Every `capabilities/<name>/capability.md` path in the router table
    must resolve to an actual file on disk."""
    text = skill_md.read_text(encoding="utf-8")
    paths = re.findall(r"capabilities/([a-z-]+)/capability\.md", text)
    assert paths, "no capability paths found in SKILL.md"
    missing = [
        p for p in paths if not (capabilities_dir / p / "capability.md").is_file()
    ]
    assert not missing, f"router lists missing capabilities: {missing}"


def test_no_orphan_capabilities(
    skill_md: Path, capabilities_dir: Path
) -> None:
    """Every capability directory under capabilities/ must be listed in the
    router table. Orphan capabilities can never be triggered."""
    text = skill_md.read_text(encoding="utf-8")
    listed = set(re.findall(r"capabilities/([a-z-]+)/capability\.md", text))
    on_disk = {
        p.name
        for p in capabilities_dir.iterdir()
        if p.is_dir() and (p / "capability.md").is_file()
    }
    orphans = on_disk - listed
    assert not orphans, f"capabilities on disk but not in router table: {orphans}"
