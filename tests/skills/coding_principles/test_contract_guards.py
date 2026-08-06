"""Contract guards for the coding-principles rule surfaces.

Three drift classes that the content-contract tests cannot catch, because they
pin counts and this file pins wording. The smells catalog anchors entries to
principles and mantras, so those anchors must name rules that exist and cite
them in the skill's own grammar; the router summarizes every principle and
mantra whose full prose lives elsewhere, so the two sides must agree on titles;
and the mantra reverse map is the documented route from a design concern to a
numbered principle, so a principle missing from it is unreachable that way.

Each guard reads the rule from the file that owns it rather than restating it
here: the citation grammar from `principles.md`, the severity convention from
the smells how-to-read section, the reverse-map exemption from the note under
the table. A convention change edits the skill, and these follow.
"""

from __future__ import annotations

import re
from pathlib import Path

_SEVERITY = r"\*(must|should|could)\*"
# The reverse map's stated exemption for principles no mantra operationalizes.
_EXEMPTION_MARKER = "**Outside the map, deliberately:"


def _principle_tags(references_dir: Path) -> dict[int, str]:
    """Map each numbered principle to its primary severity tag.

    Headings carry a conditional second tag where severity depends on context
    (17 raises to *should* on misleading names, 19 to *must* on security-
    relevant boundaries). The first tag is the one that applies by default and
    the only one an entry can be checked against without knowing the context.
    """
    text = (references_dir / "principles.md").read_text(encoding="utf-8")
    tags: dict[int, str] = {}
    for m in re.finditer(rf"^## (\d+)\. .+?—\s+{_SEVERITY}", text, flags=re.MULTILINE):
        tags[int(m.group(1))] = m.group(2)
    assert tags, "no severity-tagged principle headings found in principles.md"
    return tags


def _canonical_mantras(references_dir: Path) -> list[str]:
    """Mantra names as the tier table spells them, in file order."""
    text = (references_dir / "mantras.md").read_text(encoding="utf-8")
    names = [
        m.strip()
        for m in re.findall(r"^\|\s*(.+?)\s*\(T[123]\)\s*\|", text, flags=re.MULTILINE)
    ]
    assert names, "no tier-table mantra rows found in mantras.md"
    return names


def _expected_mantra_citations(references_dir: Path) -> list[str]:
    """The exact strings a mantra citation may use, longest first.

    `principles.md` fixes the form as the heading text lowercased, with one
    carve-out: acronyms keep their case, so `mantra SRP` is correct and
    `mantra srp` is not. Deriving both cases from the tier table keeps this
    check honest if a mantra is renamed or a new acronym is added — nothing
    here hardcodes which names are acronyms.
    """
    forms = [
        name if name.isupper() else name.lower()
        for name in _canonical_mantras(references_dir)
    ]
    return sorted(forms, key=len, reverse=True)


def _router_section(router: str, header: str) -> str:
    """The body of `header`'s section in SKILL.md, up to the next `## `.

    Both title lists must be scoped before extraction: the router numbers its
    mantra summaries and its principle titles in the same `N. **Title** —`
    shape, so a pattern applied to the whole file collects 37 entries from two
    lists and only lands on the right ones because the principles happen to
    come second and overwrite. Scoping makes that independent of section order.
    """
    assert header in router, (
        f"section not found in SKILL.md: {header!r} — if the heading was renamed,"
        " update this guard rather than letting the lookup fail obscurely"
    )
    return router.split(header, 1)[1].split("\n## ", 1)[0]


def _cited_mantra(tail: str, expected: list[str]) -> str | None:
    """The expected citation form `tail` opens with, or None.

    Longest-first so a shorter name can never shadow a longer one, and the
    character after the match must not be alphanumeric so a citation cannot
    pass by being a prefix of some longer word.
    """
    for form in expected:
        if tail.startswith(form) and (
            len(tail) == len(form) or not tail[len(form)].isalnum()
        ):
            return form
    return None


def _smell_entries(references_dir: Path) -> list[tuple[str, str, str]]:
    """Each catalog entry as (title, anchor line, severity line)."""
    text = (references_dir / "smells.md").read_text(encoding="utf-8")
    entries: list[tuple[str, str, str]] = []
    for block in re.split(r"^### ", text, flags=re.MULTILINE)[1:]:
        title = block.splitlines()[0].strip()
        anchor = re.search(r"^- \*\*Anchor:\*\*(.*)$", block, flags=re.MULTILINE)
        severity = re.search(r"^- \*\*Severity:\*\*(.*)$", block, flags=re.MULTILINE)
        if anchor and severity:
            entries.append((title, anchor.group(1), severity.group(1)))
    assert entries, "no anchored entries parsed from smells.md"
    return entries


def test_smell_anchors_name_rules_that_exist(references_dir: Path) -> None:
    """Every anchored principle number and mantra name resolves to a real rule.

    An anchor is what makes a smell a rule rather than taste, so an anchor that
    names nothing is worse than no anchor: it reads as authority and carries
    none."""
    tags = _principle_tags(references_dir)
    expected = _expected_mantra_citations(references_dir)
    problems: list[str] = []
    for title, anchor, _ in _smell_entries(references_dir):
        for num in re.findall(r"principle (\d+)", anchor):
            if int(num) not in tags:
                problems.append(f"{title!r}: anchors principle {num}, which does not exist")
        # Every `mantra ` occurrence is checked, whatever case follows it —
        # matching only lowercase would skip the acronym citations entirely
        # and let a miscased one through as if it had been validated.
        for marker in re.finditer(r"\bmantra ", anchor):
            tail = anchor[marker.end() :]
            if _cited_mantra(tail, expected) is None:
                problems.append(
                    f"{title!r}: anchors 'mantra {tail[:40].rstrip()}', which is not a"
                    " mantra name in the form the citation grammar fixes (the"
                    " mantras.md heading text lowercased; acronyms keep their case)"
                )
    assert not problems, "unresolvable smell anchors:\n" + "\n".join(problems)


def test_smell_severities_name_their_source_when_anchors_disagree(
    references_dir: Path,
) -> None:
    """Where an entry's anchors imply different severities, it says which governs.

    Principles carry tags and mantras default to *should*, so a multi-anchor
    entry can inherit two different answers. The how-to-read section requires
    the source to be named exactly there — where agreement is absent, naming is
    what resolves it; where the anchors agree there is nothing to disambiguate.
    """
    tags = _principle_tags(references_dir)
    problems: list[str] = []
    for title, anchor, severity in _smell_entries(references_dir):
        implied = {tags[int(n)] for n in re.findall(r"principle (\d+)", anchor) if int(n) in tags}
        if re.search(r"mantra ", anchor):
            implied.add("should")
        if len(implied) < 2:
            continue
        names_source = re.search(r"principle|mantra|tag|default", severity)
        if not names_source:
            stated = re.findall(_SEVERITY, severity)
            problems.append(
                f"{title!r}: anchors imply {sorted(implied)} but the entry states"
                f" {stated or ['no severity']} with no source named"
            )
    assert not problems, "unsourced severity on disagreeing anchors:\n" + "\n".join(problems)


def test_router_titles_match_the_prose_headings(skill_md: Path, references_dir: Path) -> None:
    """The router's principle and mantra titles match the files they summarize.

    The router is always loaded and the full prose is not, so a title that has
    drifted on one side is the version most readers meet. Summaries stay free
    text; only the title is pinned."""

    def normalize(text: str) -> str:
        return re.sub(r"\s+", " ", text.replace("*", "").replace("—", "-")).strip().lower()

    router = skill_md.read_text(encoding="utf-8")
    prose = (references_dir / "principles.md").read_text(encoding="utf-8")

    principles_section = _router_section(router, "## Numbered principles (titles)")
    router_principles = {
        int(m.group(1)): normalize(m.group(2))
        for m in re.finditer(
            r"^(\d+)\. \*\*(.+?)\*\*\s+—", principles_section, flags=re.MULTILINE
        )
    }
    prose_principles = {
        int(m.group(1)): normalize(m.group(2))
        for m in re.finditer(rf"^## (\d+)\. (.+?)\s+—\s+{_SEVERITY}", prose, flags=re.MULTILINE)
    }
    assert router_principles and prose_principles, "no principle titles parsed"

    problems = [
        f"principle {num}: router says {router_principles.get(num)!r},"
        f" principles.md says {prose_principles.get(num)!r}"
        for num in sorted(set(router_principles) | set(prose_principles))
        if router_principles.get(num) != prose_principles.get(num)
    ]

    # The Mantras section opens with a **Conflict resolution:** label before the
    # tier lists; it is a heading for the paragraph, not a mantra, so the titles
    # come from the numbered entries under the tier headings.
    section = _router_section(router, "## Mantras (one-line summaries)")
    router_mantras = {
        normalize(m) for m in re.findall(r"^\d+\. \*\*(.+?)\*\*", section, flags=re.MULTILINE)
    }
    canonical = {normalize(name) for name in _canonical_mantras(references_dir)}
    problems += [f"mantra in router but not mantras.md: {m!r}" for m in sorted(router_mantras - canonical)]
    problems += [f"mantra in mantras.md but not router: {m!r}" for m in sorted(canonical - router_mantras)]

    assert not problems, "router/prose title drift:\n" + "\n".join(problems)


def test_every_principle_is_reachable_from_the_reverse_map(references_dir: Path) -> None:
    """Each principle appears in a reverse-map row or in the stated exemption.

    The map is how a design concern becomes a numbered finding, so a principle
    in neither place is unreachable by that route and silently so. A deliberate
    absence is fine — it just has to be written down, which is what separates a
    decision from an omission."""
    text = (references_dir / "mantras.md").read_text(encoding="utf-8")
    mapped: set[int] = set()
    for row in re.findall(r"^\|\s*.+?\(T[123]\)\s*\|(.*?)\|\s*$", text, flags=re.MULTILINE):
        mapped.update(int(n) for n in re.findall(r"\b(\d{1,2})\b", row))

    exempt: set[int] = set()
    for line in text.splitlines():
        if line.startswith(_EXEMPTION_MARKER):
            exempt.update(int(n) for n in re.findall(r"\b(\d{1,2})\b", line))
    assert exempt, (
        "no reverse-map exemption note found — expected a line starting"
        f" {_EXEMPTION_MARKER!r} naming the principles no mantra operationalizes"
    )

    all_principles = set(_principle_tags(references_dir))
    unreachable = sorted(all_principles - mapped - exempt)
    assert not unreachable, (
        f"principles {unreachable} appear in no reverse-map row and in no stated"
        " exemption — add a row if a mantra operationalizes them, or name them in"
        f" the {_EXEMPTION_MARKER!r} note with the reason"
    )
