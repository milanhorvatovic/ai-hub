"""Cross-reference tests for the oss-repository-conventions skill.

The skill is a router (SKILL.md) plus per-domain capabilities and shared
references. SKILL.md links to `references/<name>.md` and
`capabilities/<name>/capability.md`; each capability links back to shared
references via `../../references/<name>.md`. These tests catch any of those
links breaking at change time.

The scan catalog (`references/convention-files.md`) lists hundreds of *external*
repo file paths in backticks (`CLAUDE.md`, `.github/workflows/*.yml`, …). Those
are data, not skill-internal links — so the internal-link collector matches only
`../`-traversal and `references/` / `capabilities/`-prefixed pointers, never a
bare or repo-relative catalog entry.
"""

from __future__ import annotations

import re
from pathlib import Path


def _collect_internal_links(md_path: Path) -> list[tuple[str, int]]:
    """Return (link, 1-based-line) for every backtick-quoted skill-internal
    relative `.md`/`.json` path: a `../`-traversal, or a `references/` /
    `capabilities/`-prefixed pointer. Repo-relative catalog entries are
    intentionally not matched (they don't carry those prefixes)."""
    text = md_path.read_text(encoding="utf-8")
    out: list[tuple[str, int]] = []
    for lineno, line in enumerate(text.splitlines(), start=1):
        for m in re.finditer(
            r"`((?:(?:\.\./)+[A-Za-z0-9_./-]+"
            r"|(?:references|capabilities)/[A-Za-z0-9_./-]+)\.(?:md|json))`",
            line,
        ):
            out.append((m.group(1), lineno))
    return out


def test_skill_md_reference_links_resolve(
    skill_md: Path, references_dir: Path
) -> None:
    """Every `references/<name>.md` linked from SKILL.md must exist."""
    text = skill_md.read_text(encoding="utf-8")
    referenced = re.findall(r"references/([A-Za-z0-9_./-]+\.md)", text)
    assert referenced, "SKILL.md links no reference files"
    missing = [r for r in referenced if not (references_dir / r).is_file()]
    assert not missing, f"SKILL.md references missing files: {missing}"


def test_skill_md_capability_links_resolve(
    skill_md: Path, capabilities_dir: Path
) -> None:
    """Every `capabilities/<name>/<file>.md` linked from SKILL.md must exist."""
    text = skill_md.read_text(encoding="utf-8")
    referenced = re.findall(r"capabilities/([A-Za-z0-9_./-]+\.md)", text)
    assert referenced, "SKILL.md routes to no capabilities"
    missing = [r for r in referenced if not (capabilities_dir / r).is_file()]
    assert not missing, f"SKILL.md routes to missing capabilities: {missing}"


def test_internal_links_resolve_and_stay_in_tree(skill_root: Path) -> None:
    """Every skill-internal relative link across the skill tree resolves to a
    file inside the tree — no `../` chain escapes the skill directory. Covers
    SKILL.md and every capability.md (which link to `../../references/...`)."""
    skill_root_resolved = skill_root.resolve()
    broken: list[str] = []
    for md in sorted(skill_root.rglob("*.md")):
        for link, lineno in _collect_internal_links(md):
            target = (md.parent / link).resolve()
            rel = f"{md.relative_to(skill_root)}:{lineno} -> {link}"
            if not target.is_relative_to(skill_root_resolved):
                broken.append(f"{rel} (escapes skill tree)")
            elif not target.is_file():
                broken.append(rel)
    assert not broken, "broken internal links:\n" + "\n".join(broken)
