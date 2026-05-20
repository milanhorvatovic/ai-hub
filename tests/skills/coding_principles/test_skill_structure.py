"""Structural tests for skills/coding-principles/SKILL.md.

Validates the router file's frontmatter, version, capability table, that every
capability referenced in the router exists on disk (and vice versa — no orphan
capabilities the router does not advertise), and that each language capability
carries the documented eight-file set.
"""

from __future__ import annotations

import re
from pathlib import Path

# The four language capability directories each carry the same eight-file set
# (see the "File layout" section of SKILL.md). `review` is a workflow
# capability, not a language one, so it is exempt from this invariant.
LANGUAGE_CAPABILITIES = ("bash", "python", "rust", "typescript")
LANGUAGE_CAPABILITY_FILES = frozenset(
    {
        "capability.md",
        "anti-patterns.md",
        "examples.md",
        "best-practices.md",
        "concurrency.md",
        "dependencies.md",
        "performance.md",
        "project-structure.md",
    }
)


def _parse_frontmatter(md_path: Path) -> dict[str, str]:
    """Parse a leading YAML frontmatter block into a flat dict.

    Hand-rolled because the skill's tests run with Python stdlib only — no
    PyYAML dependency. Supports exactly what skill frontmatter uses: flat
    `key: value` pairs and the multi-line `>` folded scalar (descriptions).
    Nested mappings are NOT parsed — an indented child of a plain key (e.g.
    `metadata:` -> `version:`) is skipped, not turned into a sub-key, so
    callers must not rely on this for nested data.
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
        if raw.startswith("  "):
            # Indented line that is not a folded/literal continuation — i.e. a
            # nested mapping child like `metadata:` -> `version:`. Skipped on
            # purpose: this parser supports only flat keys plus `>`/`|` scalars
            # (see docstring), so nested keys are dropped, not mis-parsed.
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
    assert fm["name"] == "coding-principles"


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
    """Every `capabilities/<name>/capability.md` path in the router table
    must resolve to an actual file on disk."""
    text = skill_md.read_text(encoding="utf-8")
    paths = re.findall(r"capabilities/([a-z-]+)/capability\.md", text)
    assert paths, "no capability paths found in SKILL.md"
    missing = [
        p for p in paths if not (capabilities_dir / p / "capability.md").is_file()
    ]
    assert not missing, f"router lists missing capabilities: {missing}"


def test_no_orphan_capabilities(skill_md: Path, capabilities_dir: Path) -> None:
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


def test_language_capabilities_carry_the_eight_file_set(
    capabilities_dir: Path,
) -> None:
    """Each language capability directory must carry exactly the documented
    eight-file set. A missing file means a capability load silently degrades;
    an extra one means the layout drifted from what SKILL.md advertises."""
    mismatches: list[str] = []
    for lang in LANGUAGE_CAPABILITIES:
        lang_dir = capabilities_dir / lang
        assert lang_dir.is_dir(), f"language capability missing: {lang}"
        present = {p.name for p in lang_dir.iterdir() if p.is_file()}
        if present != set(LANGUAGE_CAPABILITY_FILES):
            missing = sorted(LANGUAGE_CAPABILITY_FILES - present)
            extra = sorted(present - LANGUAGE_CAPABILITY_FILES)
            mismatches.append(f"{lang}: missing={missing} extra={extra}")
    assert not mismatches, "language capability file-set drift:\n" + "\n".join(
        mismatches
    )
