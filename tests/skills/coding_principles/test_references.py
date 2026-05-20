"""Cross-reference tests for coding-principles capabilities and references.

Capabilities link to reference files via relative paths like
`../../references/<name>.md`, and SKILL.md links to `references/<name>.md`. A
capability or router pointing at a missing reference degrades silently at load
time; these tests catch the broken link at change time.

(Unlike git-toolkit, this skill ships no JSON Schema artifact, so there are no
schema-validity tests here.)
"""

from __future__ import annotations

import re
from pathlib import Path


def _collect_relative_links(md_path: Path) -> list[tuple[str, int]]:
    """Return (relative-link, 1-based-line-number) for every backtick-quoted
    relative `.md`/`.json` path into the skill tree.

    Matches skill-internal relative links ending in `.md` or `.json`, in
    either form: a `../`-prefixed traversal (e.g. `../../references/foo.md`),
    or a `references/` / `capabilities/` prefix (as used from SKILL.md). Bare
    prose mentions like `principles.md` and skill-root-relative pointers used
    inside reference prose are intentionally not treated as filesystem-relative
    links here — only capability.md links (which use `../` traversal) and
    SKILL.md's `references/` / `capabilities/` pointers are resolved.
    """
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


def test_capability_links_resolve(
    skill_root: Path, capabilities_dir: Path
) -> None:
    """Every relative path linked from a capability.md must resolve to a file
    that stays inside the skill tree. A link that escapes the tree via `../`
    (e.g. `../../../../README.md`) is reported as broken even if it exists —
    the test validates *skill-internal* links only."""
    broken: list[str] = []
    skill_root_resolved = skill_root.resolve()
    for cap_dir in sorted(capabilities_dir.iterdir()):
        cap_md = cap_dir / "capability.md"
        if not cap_md.is_file():
            continue
        for link, lineno in _collect_relative_links(cap_md):
            target = (cap_md.parent / link).resolve()
            rel = f"{cap_md.relative_to(skill_root)}:{lineno} -> {link}"
            if not target.is_relative_to(skill_root_resolved):
                broken.append(f"{rel} (escapes skill tree)")
            elif not target.is_file():
                broken.append(rel)
    assert not broken, "broken relative links in capabilities:\n" + "\n".join(
        broken
    )


def test_skill_md_reference_links_resolve(
    skill_md: Path, references_dir: Path
) -> None:
    """Every `references/<name>.md` linked from SKILL.md must exist."""
    text = skill_md.read_text(encoding="utf-8")
    referenced = re.findall(r"references/([A-Za-z0-9_./-]+\.md)", text)
    missing = [r for r in referenced if not (references_dir / r).is_file()]
    assert not missing, f"SKILL.md references missing files: {missing}"


def test_skill_md_capability_links_resolve(
    skill_md: Path, capabilities_dir: Path
) -> None:
    """Every `capabilities/<name>/<file>.md` linked from SKILL.md must exist.

    Catches stale pointers like a `references/review-mode.md` link left behind
    after review-mode was promoted to `capabilities/review/capability.md`."""
    text = skill_md.read_text(encoding="utf-8")
    referenced = re.findall(r"capabilities/([A-Za-z0-9_./-]+\.md)", text)
    missing = [r for r in referenced if not (capabilities_dir / r).is_file()]
    assert not missing, f"SKILL.md references missing capabilities: {missing}"


def test_reference_file_pointers_resolve(skill_root: Path) -> None:
    """Pointers inside reference prose must resolve too.

    Reference files use two link conventions: skill-root-relative pointers
    (`capabilities/<x>.md`, `references/<x>.md` — resolved from the skill root,
    the way SKILL.md writes them) and `../`-traversal links (resolved from the
    file's own directory). Both are checked here so a stale pointer buried in a
    reference — e.g. a link to a since-promoted file — fails at change time
    rather than degrading silently at load. Bare prose mentions without a
    `capabilities/`, `references/`, or `../` prefix are intentionally ignored.
    A pointer that resolves outside the skill tree is reported as an escape, so
    a stray `../../../../something.md` cannot pass just because it exists."""
    refs_dir = skill_root / "references"
    skill_root_resolved = skill_root.resolve()
    broken: list[str] = []
    for md in sorted(refs_dir.glob("*.md")):
        for lineno, line in enumerate(
            md.read_text(encoding="utf-8").splitlines(), start=1
        ):
            for m in re.finditer(
                r"`((?:\.\./[A-Za-z0-9_./-]+"
                r"|(?:references|capabilities)/[A-Za-z0-9_./-]+)\.(?:md|json))`",
                line,
            ):
                link = m.group(1)
                base = md.parent if link.startswith("../") else skill_root
                target = (base / link).resolve()
                rel = f"{md.relative_to(skill_root)}:{lineno} -> {link}"
                if not target.is_relative_to(skill_root_resolved):
                    broken.append(f"{rel} (escapes skill tree)")
                elif not target.is_file():
                    broken.append(rel)
    assert not broken, "broken pointers in reference files:\n" + "\n".join(broken)
