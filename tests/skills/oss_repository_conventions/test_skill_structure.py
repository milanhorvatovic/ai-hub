"""Structural tests for skills/oss-repository-conventions/SKILL.md.

Validates the skill's frontmatter, version, and declared tools. Unlike
git-toolkit and coding-principles, oss-repository-conventions is a single-file skill
(no router table, no capabilities/), so this suite asserts that shape rather
than capability-registration consistency.
"""

from __future__ import annotations

import re
from pathlib import Path


def _parse_frontmatter(md_path: Path) -> dict[str, str]:
    """Parse a leading YAML frontmatter block into a flat dict.

    Hand-rolled because the skill's tests run with Python stdlib only — no
    PyYAML dependency. Handles flat key: value pairs and the multi-line `>`
    folded string used in skill descriptions. `read_text` opens in universal-
    newline mode, so CRLF checkouts (Windows / core.autocrlf) are already
    normalized to LF before parsing.
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
    assert fm["name"] == "oss-repository-conventions"


def test_skill_declares_allowed_tools(skill_md: Path) -> None:
    fm = _parse_frontmatter(skill_md)
    assert fm.get("allowed-tools"), "frontmatter missing `allowed-tools`"


def test_skill_version_is_semver(skill_md: Path) -> None:
    text = skill_md.read_text(encoding="utf-8")
    m = re.search(r'^\s+version:\s*"([^"]+)"', text, flags=re.MULTILINE)
    assert m, "no version: key found in metadata"
    version = m.group(1)
    semver = re.fullmatch(
        r"\d+\.\d+\.\d+(-[0-9A-Za-z.-]+)?(\+[0-9A-Za-z.-]+)?", version
    )
    assert semver, f"version `{version}` is not semver"


def test_is_single_file_skill(skill_root: Path) -> None:
    """oss-repository-conventions is intentionally not a router. If a capabilities/
    directory appears, the skill has grown a router shape and these structural
    tests (and the reference checks) need to be reconsidered."""
    assert not (skill_root / "capabilities").exists(), (
        "oss-repository-conventions gained a capabilities/ directory; it is no longer a "
        "single-file skill — update its tests to validate the router table"
    )


def test_references_catalog_present(references_dir: Path) -> None:
    assert (references_dir / "convention-files.md").is_file(), (
        "references/convention-files.md missing"
    )
