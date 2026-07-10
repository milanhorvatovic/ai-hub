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
    """Every relative path linked from any capability file — `capability.md`
    or a file in its `references/` subdir — must resolve to a file that stays
    inside the skill tree. A link that escapes the tree via `../` (e.g.
    `../../../../README.md`) is reported as broken even if it exists — the test
    validates *skill-internal* links only."""
    broken: list[str] = []
    skill_root_resolved = skill_root.resolve()
    for md in sorted(capabilities_dir.rglob("*.md")):
        for link, lineno in _collect_relative_links(md):
            target = (md.parent / link).resolve()
            rel = f"{md.relative_to(skill_root)}:{lineno} -> {link}"
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
    """Backtick-quoted file pointers inside reference prose must resolve.

    Reference files link with standard-markdown, file-relative paths: bare
    same-directory filenames (`observability.md`) and `../`-traversal links
    (`../capabilities/<lang>/references/foo.md`). Both resolve relative to the
    file that contains them, per the foundry path-resolution rule — there is no
    skill-root base.

    A backtick-quoted `*.md`/`*.json` token is checked as a pointer when it is
    unambiguous:

    - any token containing `/` (a `../`-traversal or directory-bearing path) is
      always a pointer — resolved file-relative and required to exist; this
      catches a stale skill-root-relative leftover like `references/foo.md`
      (which resolves to `references/references/foo.md` and fails), and a
      `../`-chain that escapes the skill tree is reported as an escape;
    - a bare filename (no `/`) is checked only when it names an actual
      reference sibling, so prose mentions of external files (`package.json`,
      `CLAUDE.md`, …) and of capability files (`best-practices.md`) are not
      mistaken for same-directory pointers.

    Non-backtick prose mentions are ignored entirely."""
    skill_root_resolved = skill_root.resolve()
    ref_siblings = {p.name for p in (skill_root / "references").glob("*.md")}
    broken: list[str] = []
    # Any backtick-quoted path ending in .md/.json (bare, ../-traversal, or
    # directory-bearing); the gate below decides which are skill-internal.
    link_re = re.compile(r"`([A-Za-z0-9_./-]+\.(?:md|json))`")
    for md in sorted((skill_root / "references").glob("*.md")):
        for lineno, line in enumerate(
            md.read_text(encoding="utf-8").splitlines(), start=1
        ):
            for m in link_re.finditer(line):
                link = m.group(1)
                if "/" not in link and link not in ref_siblings:
                    continue  # bare external / capability-file prose mention
                target = (md.parent / link).resolve()  # standard-markdown, file-relative
                rel = f"{md.relative_to(skill_root)}:{lineno} -> {link}"
                if not target.is_relative_to(skill_root_resolved):
                    broken.append(f"{rel} (escapes skill tree)")
                elif not target.is_file():
                    broken.append(rel)
    assert not broken, "broken pointers in reference files:\n" + "\n".join(broken)


LANGUAGES = ("bash", "python", "rust", "typescript")


def test_example_pointers_match_example_headings(
    references_dir: Path, capabilities_dir: Path
) -> None:
    """Two-way contract between principles.md "Code examples" pointer lines and
    the per-language `examples.md` headings.

    Forward: every language named on a principle's pointer line must have a
    matching `## Principle N` heading in its examples file. Reverse: every
    `## Principle N` heading in every examples file must be named on principle
    N's pointer line — an example nobody points at is invisible drift (the
    python P8 case). Mantra-titled headings (`## Mantra — …`) are outside the
    numbered mapping and exempt."""
    principles = (references_dir / "principles.md").read_text(encoding="utf-8")
    pointed: dict[int, set[str]] = {}
    current: int | None = None
    for line in principles.splitlines():
        if m := re.match(r"^## (\d+)\.", line):
            current = int(m.group(1))
            continue
        if "**Code examples**" in line:
            assert current is not None, f"pointer line before any principle: {line!r}"
            langs = {
                lang
                for lang in LANGUAGES
                if re.search(rf"\b{lang}\b", line, flags=re.IGNORECASE)
            }
            assert langs, f"pointer line names no known language: {line!r}"
            pointed[current] = langs

    demonstrated: dict[int, set[str]] = {}
    for lang in LANGUAGES:
        examples = capabilities_dir / lang / "references" / "examples.md"
        for m in re.finditer(
            r"^## Principle (\d+)\b",
            examples.read_text(encoding="utf-8"),
            flags=re.MULTILINE,
        ):
            demonstrated.setdefault(int(m.group(1)), set()).add(lang)

    problems: list[str] = []
    for num, langs in sorted(pointed.items()):
        if missing := langs - demonstrated.get(num, set()):
            problems.append(
                f"principle {num}: pointer names {sorted(missing)} but their"
                f" examples.md has no '## Principle {num}' heading"
            )
    for num, langs in sorted(demonstrated.items()):
        if unpointed := langs - pointed.get(num, set()):
            problems.append(
                f"principle {num}: {sorted(unpointed)} demonstrate it but the"
                " pointer line omits them"
            )
    assert not problems, "pointer/example drift:\n" + "\n".join(problems)
