"""Content-contract tests for the coding-principles skill.

The router advertises specific, countable facts about the skill's body —
"16 mantras", "21 numbered principles", the per-language seven-file reference
set — and the capabilities use portable name slugs. These tests pin those
numbers, the file set, and the slug pattern so the prose, the reference files,
and the SKILL.md summary lists cannot drift apart silently (e.g. someone adds
a 22nd principle to principles.md but forgets the router's titles list, or
renames a capability without updating its slug).
"""

from __future__ import annotations

import re
from pathlib import Path

EXPECTED_MANTRAS = 16
EXPECTED_PRINCIPLES = 21


def _section(text: str, header_prefix: str) -> str:
    """Return the body of the first `## ` section whose header starts with
    `header_prefix`, up to the next `## ` header (or end of file)."""
    lines = text.splitlines()
    start = next(
        (i for i, line in enumerate(lines) if line.startswith(header_prefix)), None
    )
    assert start is not None, f"section not found: {header_prefix!r}"
    end = next(
        (i for i in range(start + 1, len(lines)) if lines[i].startswith("## ")),
        len(lines),
    )
    return "\n".join(lines[start + 1 : end])


def _numbered_items(block: str) -> list[int]:
    """Leading `N. ` ordinals of a numbered list block, in order."""
    return [
        int(m.group(1))
        for line in block.splitlines()
        if (m := re.match(r"^(\d+)\.\s", line))
    ]


def test_mantra_count_is_consistent(skill_md: Path, references_dir: Path) -> None:
    """16 mantras in mantras.md (across the three tiers), 16 numbered summaries
    in the router, and the file-layout table's "16 mantras" claim all agree."""
    mantras_md = (references_dir / "mantras.md").read_text(encoding="utf-8")
    # Count bold-bullet mantras within each tier section explicitly. (Spanning
    # from "## Tier 1" to a "## Mantra" marker only worked because it matched
    # the reverse-map header — fragile if another "## Mantra"-prefixed section
    # were ever added inside the tiers.)
    bullets = [
        line
        for tier in ("## Tier 1", "## Tier 2", "## Tier 3")
        for line in _section(mantras_md, tier).splitlines()
        if line.startswith("- **")
    ]
    assert len(bullets) == EXPECTED_MANTRAS, (
        f"mantras.md has {len(bullets)} tier bullets, expected {EXPECTED_MANTRAS}"
    )

    summary = _numbered_items(_section(skill_md.read_text(encoding="utf-8"), "## Mantras"))
    assert summary == list(range(1, EXPECTED_MANTRAS + 1)), (
        f"router mantra summaries are {summary}, expected 1..{EXPECTED_MANTRAS}"
    )

    text = skill_md.read_text(encoding="utf-8")
    assert f"all {EXPECTED_MANTRAS} mantras" in text, (
        "file-layout table no longer claims 'all 16 mantras' — update the count"
    )


def test_principle_count_is_consistent(
    skill_md: Path, references_dir: Path
) -> None:
    """21 principle headings in principles.md, 21 numbered titles in the
    router, and the description's "21 numbered principles" claim all agree."""
    principles_md = (references_dir / "principles.md").read_text(encoding="utf-8")
    headings = re.findall(r"^#{2,3} (\d+)\.", principles_md, flags=re.MULTILINE)
    assert [int(h) for h in headings] == list(range(1, EXPECTED_PRINCIPLES + 1)), (
        f"principles.md headings are {headings}, expected 1..{EXPECTED_PRINCIPLES}"
    )

    titles = _numbered_items(
        _section(skill_md.read_text(encoding="utf-8"), "## Numbered principles")
    )
    assert titles == list(range(1, EXPECTED_PRINCIPLES + 1)), (
        f"router principle titles are {titles}, expected 1..{EXPECTED_PRINCIPLES}"
    )

    assert f"{EXPECTED_PRINCIPLES} numbered principles" in skill_md.read_text(
        encoding="utf-8"
    ), "description no longer claims '21 numbered principles' — update the count"


def test_language_capabilities_carry_the_documented_file_set(
    capabilities_dir: Path,
    language_capabilities: tuple[str, ...],
    language_reference_files: frozenset[str],
) -> None:
    """Each language capability must be `capability.md` plus a `references/`
    subdir holding exactly the seven supporting files. A missing file means a
    capability load silently degrades; an extra one means the layout drifted
    from what SKILL.md advertises."""
    mismatches: list[str] = []
    for lang in language_capabilities:
        lang_dir = capabilities_dir / lang
        assert (lang_dir / "capability.md").is_file(), (
            f"{lang}: missing capability.md entry point"
        )
        refs = lang_dir / "references"
        assert refs.is_dir(), f"{lang}: missing references/ subdir"
        present = {p.name for p in refs.iterdir() if p.is_file()}
        if present != set(language_reference_files):
            missing = sorted(language_reference_files - present)
            extra = sorted(present - language_reference_files)
            mismatches.append(f"{lang}/references: missing={missing} extra={extra}")
    assert not mismatches, "language capability file-set drift:\n" + "\n".join(
        mismatches
    )


def test_capability_name_slugs_follow_pattern(capabilities_dir: Path) -> None:
    """Each capability.md frontmatter `name` is `coding-principles-<dir>`, the
    portable slug the router documents."""
    mismatches: list[str] = []
    for cap_dir in sorted(capabilities_dir.iterdir()):
        cap_md = cap_dir / "capability.md"
        if not cap_md.is_file():
            continue
        m = re.search(
            r"^name:\s*(\S+)", cap_md.read_text(encoding="utf-8"), flags=re.MULTILINE
        )
        actual = m.group(1) if m else None
        expected = f"coding-principles-{cap_dir.name}"
        if actual != expected:
            mismatches.append(f"{cap_dir.name}: name={actual!r}, expected {expected!r}")
    assert not mismatches, "capability slug drift:\n" + "\n".join(mismatches)
