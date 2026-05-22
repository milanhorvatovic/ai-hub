"""Structural tests for skills/oss-repository-conventions/SKILL.md.

Validates the router's frontmatter, version, capability-table consistency
(every routed path exists; no capability on disk is left unrouted), and the
allowed-tools union invariant — the router must declare at least every tool any
capability declares.
"""

from __future__ import annotations

import re
from pathlib import Path


def _parse_frontmatter(md_path: Path) -> dict[str, str]:
    """Parse a leading YAML frontmatter block into a flat dict.

    Hand-rolled because the skill's tests run with Python stdlib only — no
    PyYAML dependency. Handles flat key: value pairs and the multi-line `>`
    folded string used in skill descriptions. `read_text` opens in universal-
    newline mode, so CRLF checkouts are normalized to LF before parsing.
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


def _tools(value: str) -> set[str]:
    """Split an `allowed-tools` value (space-separated) into a set."""
    return {t for t in re.split(r"\s+", value.strip()) if t}


def test_skill_md_exists(skill_md: Path) -> None:
    assert skill_md.is_file(), f"{skill_md} not found"


def test_skill_md_has_frontmatter(skill_md: Path) -> None:
    fm = _parse_frontmatter(skill_md)
    assert "name" in fm, "frontmatter missing required `name`"
    assert "description" in fm, "frontmatter missing required `description`"
    assert fm["name"] == "oss-repository-conventions"


def test_skill_declares_allowed_tools(skill_md: Path) -> None:
    fm = _parse_frontmatter(skill_md)
    assert fm.get("allowed-tools"), "router frontmatter missing `allowed-tools`"


def test_skill_version_is_semver(skill_md: Path) -> None:
    text = skill_md.read_text(encoding="utf-8")
    m = re.search(r'^\s+version:\s*"([^"]+)"', text, flags=re.MULTILINE)
    assert m, "no version: key found in metadata"
    version = m.group(1)
    semver = re.fullmatch(
        r"\d+\.\d+\.\d+(-[0-9A-Za-z.-]+)?(\+[0-9A-Za-z.-]+)?", version
    )
    assert semver, f"version `{version}` is not semver"


def test_capability_table_lists_existing_paths(
    skill_md: Path, capabilities_dir: Path
) -> None:
    """Every `capabilities/<name>/capability.md` routed from SKILL.md must
    resolve to an actual file on disk."""
    text = skill_md.read_text(encoding="utf-8")
    paths = re.findall(r"capabilities/([a-z-]+)/capability\.md", text)
    assert paths, "no capability paths found in SKILL.md routing table"
    missing = [
        p for p in paths if not (capabilities_dir / p / "capability.md").is_file()
    ]
    assert not missing, f"router routes to missing capabilities: {missing}"


def test_no_orphan_capabilities(
    skill_md: Path, capabilities_dir: Path
) -> None:
    """Every capability directory on disk must be routed from SKILL.md.

    A capability that exists but isn't in the routing table can never be
    triggered. (Roadmap entries are name-only and not yet on disk, so they
    don't count as orphans.)"""
    if not capabilities_dir.is_dir():
        return
    text = skill_md.read_text(encoding="utf-8")
    routed = set(re.findall(r"capabilities/([a-z-]+)/capability\.md", text))
    on_disk = {
        p.name
        for p in capabilities_dir.iterdir()
        if p.is_dir() and (p / "capability.md").is_file()
    }
    orphans = on_disk - routed
    assert not orphans, f"capabilities on disk but not routed: {orphans}"


def test_every_capability_has_frontmatter(capabilities_dir: Path) -> None:
    """Each capability declares its own name and allowed-tools."""
    if not capabilities_dir.is_dir():
        return
    bad: list[str] = []
    for cap in sorted(capabilities_dir.glob("*/capability.md")):
        fm = _parse_frontmatter(cap)
        if not fm.get("name") or not fm.get("allowed-tools"):
            bad.append(str(cap.parent.name))
    assert not bad, f"capabilities missing name/allowed-tools: {bad}"


def test_router_allowed_tools_is_superset_of_capabilities(
    skill_md: Path, capabilities_dir: Path
) -> None:
    """The router's allowed-tools must be a superset of the union of every
    capability's allowed-tools (router = union; capabilities never need a tool
    the router can't grant)."""
    router_tools = _tools(_parse_frontmatter(skill_md).get("allowed-tools", ""))
    if not capabilities_dir.is_dir():
        return
    union: set[str] = set()
    for cap in capabilities_dir.glob("*/capability.md"):
        union |= _tools(_parse_frontmatter(cap).get("allowed-tools", ""))
    missing = union - router_tools
    assert not missing, (
        f"router allowed-tools missing tools used by capabilities: {missing}"
    )
