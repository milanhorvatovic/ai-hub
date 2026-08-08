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
from datetime import UTC, datetime
from pathlib import Path

# Either emphasis marker: which character spells italics is Prettier's call, not
# the skill's, and the guard asserts the tag rather than the formatter's choice.
# The pair still has to match and stand alone, so a doubled `**must**` and a stray
# `*must_` — which renders as no emphasis at all — stay rejected. The backreference
# is named because this pattern is interpolated at two different group offsets, so
# a numbered one would point at the wrong group in one of them.
_SEVERITY = r"(?<![*_])(?P<marker>[*_])(?P<severity>must|should|could)(?P=marker)(?![*_])"
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
        tags[int(m.group(1))] = m.group("severity")
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
            stated = [m.group("severity") for m in re.finditer(_SEVERITY, severity)]
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


_STAMP = re.compile(r"were last checked (\d{4})-(\d{2})\.\*\*")


# Per-language reference filenames that carry tool and runtime recommendations,
# and the two that carry none — anti-patterns is language semantics, examples is
# code. Filename-driven so a newly added language inherits the whole contract
# without anyone enrolling it.
_CLAIM_BEARING = frozenset(
    {"best-practices.md", "concurrency.md", "dependencies.md", "performance.md",
     "project-structure.md"}
)
_CLAIM_FREE = frozenset({"anti-patterns.md", "examples.md"})

# Shared references classified one by one, because no filename convention
# separates them. Every file directly under references/ must appear in exactly
# one bucket — a new one in neither fails this test rather than slipping past.
_SHARED_STAMPED = frozenset(
    {"api-design.md", "configuration.md", "data-handling.md", "observability.md",
     "persistence.md", "platform-matrix.md", "resilience.md", "testing.md"}
)
_SHARED_CLAIM_FREE = frozenset(
    {"architecture.md", "glossary.md", "language-expansion.md", "mantras.md",
     "principles.md", "refactoring.md", "smells.md"}
)

# The workflow capabilities are classified per (capability, file) rather than by
# filename, because `best-practices.md` means different things in the two: the
# comments one argues that detection tooling — not taste — decides whether a
# docstring is required, so the tools it names are load-bearing, while the review
# one is about phrasing and severity and names none. That is the line everywhere
# here: owning a recommendation earns the stamp, mentioning one while making a
# different argument does not.
_WORKFLOW_REFERENCES = {
    ("comments", "best-practices.md"): True,
    ("comments", "anti-patterns.md"): False,
    ("comments", "by-file-type.md"): False,
    ("review", "best-practices.md"): False,
    ("review", "examples.md"): False,
}


def test_currency_stamps_cover_every_claim_bearing_reference(
    skill_root: Path,
    capabilities_dir: Path,
    references_dir: Path,
    language_capabilities: tuple[str, ...],
) -> None:
    """The stamped set is exactly the files that carry decaying claims.

    This fails closed, which the first version of it did not: detecting "does
    this recommend a tool?" by matching a vocabulary of backticked names misses
    every tool nobody thought to list and every runtime-version claim, so the
    test stayed green while the router promised full coverage. Classification is
    structural instead — by filename inside a language capability, and per file
    for the shared references, where an unclassified file is a failure.

    Capability entry points carry no stamp by design: they summarize what their
    references cover, so a second date there could only drift from the first.
    """
    problems: list[str] = []

    def check(md: Path, expect_stamp: bool) -> None:
        rel = md.relative_to(skill_root).as_posix()
        stamp = _STAMP.search(md.read_text(encoding="utf-8"))
        if expect_stamp and not stamp:
            problems.append(f"{rel}: carries decaying claims but no currency stamp")
        elif not expect_stamp and stamp:
            problems.append(f"{rel}: stamped, but classified as carrying no decaying claims")
        elif stamp:
            year, month = int(stamp.group(1)), int(stamp.group(2))
            now = datetime.now(UTC)
            if not (2020 <= year and 1 <= month <= 12):
                problems.append(f"{rel}: unparseable stamp {stamp.group(0)!r}")
            elif (year, month) > (now.year, now.month):
                # "last checked" cannot be ahead of now; a typo like 2099-01 would
                # otherwise inherit the same trust as a real verification date.
                problems.append(f"{rel}: stamp {year}-{month:02d} is in the future")

    for refs in sorted(capabilities_dir.glob("*/references")):
        is_language = refs.parent.name in language_capabilities
        for md in sorted(refs.glob("*.md")):
            workflow = _WORKFLOW_REFERENCES.get((refs.parent.name, md.name))
            if is_language and md.name in _CLAIM_BEARING:
                check(md, expect_stamp=True)
            elif is_language and md.name in _CLAIM_FREE:
                check(md, expect_stamp=False)
            elif not is_language and workflow is not None:
                check(md, expect_stamp=workflow)
            else:
                problems.append(
                    f"{md.relative_to(skill_root).as_posix()}: unclassified reference —"
                    " decide whether it carries decaying claims and add it to a set"
                )

    for md in sorted(references_dir.glob("*.md")):
        if md.name in _SHARED_STAMPED:
            check(md, expect_stamp=True)
        elif md.name in _SHARED_CLAIM_FREE:
            check(md, expect_stamp=False)
        else:
            problems.append(
                f"{md.relative_to(skill_root).as_posix()}: unclassified shared reference —"
                " decide whether it carries decaying claims and add it to a set"
            )

    assert not problems, "currency-stamp coverage:\n" + "\n".join(problems)


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
