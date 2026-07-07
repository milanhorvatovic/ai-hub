"""Cross-reference tests for skills/behavior-coach/references/.

The router loads reference files by relative path at each pipeline stage; a
broken or orphaned reference silently degrades the load. These tests catch
both directions of drift at change time.
"""

from __future__ import annotations

import re
from pathlib import Path


def _referenced_files(skill_md: Path) -> set[str]:
    text = skill_md.read_text(encoding="utf-8")
    return set(re.findall(r"references/([A-Za-z0-9_.-]+\.md)", text))


def test_skill_md_reference_links_resolve(
    skill_md: Path, references_dir: Path
) -> None:
    """Every `references/<name>.md` mentioned in SKILL.md must exist."""
    referenced = _referenced_files(skill_md)
    assert referenced, "SKILL.md mentions no reference files"
    missing = [r for r in referenced if not (references_dir / r).is_file()]
    assert not missing, f"SKILL.md references missing files: {missing}"


def test_no_orphan_references(skill_md: Path, references_dir: Path) -> None:
    """Every file in references/ must be reachable from the router —
    an unmentioned reference can never be loaded."""
    referenced = _referenced_files(skill_md)
    on_disk = {p.name for p in references_dir.glob("*.md")}
    orphans = on_disk - referenced
    assert not orphans, f"references on disk but not in SKILL.md: {orphans}"


def test_each_reference_has_h1_title(references_dir: Path) -> None:
    """Reference files open with an H1 so a partial load still identifies
    which stage's procedure it is."""
    missing = [
        p.name
        for p in sorted(references_dir.glob("*.md"))
        if not p.read_text(encoding="utf-8").startswith("# ")
    ]
    assert not missing, f"references without a leading H1: {missing}"
