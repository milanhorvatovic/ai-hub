"""Content-coupling tests between coding-principles reference files.

Generic link/pointer resolution across the skill tree lives in the fleet-wide
suite (`tests/skills/test_structure_all.py`); what stays here is the contract
that is unique to this skill — the two-way coupling between principles.md
"Code examples" pointer lines and the per-language example files.
"""

from __future__ import annotations

import re
from pathlib import Path


def test_example_pointers_match_example_headings(
    references_dir: Path, capabilities_dir: Path, language_capabilities: tuple[str, ...]
) -> None:
    """Two-way contract between principles.md "Code examples" pointer lines and
    the per-language `examples.md` headings.

    Forward: every language named on a principle's pointer line must have a
    matching `## Principle N` heading in its examples file. Reverse: every
    `## Principle N` heading in every examples file must be named on principle
    N's pointer line — an example nobody points at is invisible drift (the
    python P8 case). Mantra-titled headings (`## Mantra — …`) are outside the
    numbered mapping and exempt.

    The language set comes from the declared list, not from which capabilities
    happen to ship an `examples.md`: the review capability ships one too — a
    worked review, not per-principle code — and discovering by filename would
    silently enrol it, leaving the contract correct only for as long as no
    pointer line contains the word "review"."""
    languages = sorted(language_capabilities)
    missing = [
        lang
        for lang in languages
        if not (capabilities_dir / lang / "references" / "examples.md").is_file()
    ]
    assert not missing, f"declared language capabilities ship no examples.md: {missing}"

    principles = (references_dir / "principles.md").read_text(encoding="utf-8")
    pointed: dict[int, set[str]] = {}
    current: int | None = None
    for line in principles.splitlines():
        if m := re.match(r"^## (\d+)\.", line):
            current = int(m.group(1))
            continue
        # Anchored, not a substring search: pointer lines are always the
        # blockquote form, and prose that merely names the marker — the
        # citation-grammar section documenting it — is not a pointer.
        if line.startswith("> **Code examples**"):
            assert current is not None, f"pointer line before any principle: {line!r}"
            # \b is safe at both edges: capability dir names are constrained
            # to lowercase+hyphens, and hyphens are interior when present.
            langs = {
                lang
                for lang in languages
                if re.search(rf"\b{re.escape(lang)}\b", line, flags=re.IGNORECASE)
            }
            assert langs, f"pointer line names no known language: {line!r}"
            pointed.setdefault(current, set()).update(langs)

    demonstrated: dict[int, set[str]] = {}
    for lang in languages:
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
