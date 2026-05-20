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
    """Every relative path linked from a capability.md must resolve."""
    broken: list[str] = []
    for cap_dir in sorted(capabilities_dir.iterdir()):
        cap_md = cap_dir / "capability.md"
        if not cap_md.is_file():
            continue
        for link, lineno in _collect_relative_links(cap_md):
            target = (cap_md.parent / link).resolve()
            if not target.is_file():
                broken.append(
                    f"{cap_md.relative_to(skill_root)}:{lineno} -> {link}"
                )
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
