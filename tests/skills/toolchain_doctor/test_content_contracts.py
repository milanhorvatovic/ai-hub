"""Contracts the parametrized structural suite cannot know about.

The generic checks already hold this skill to frontmatter shape, router-to-
capability routing in both directions, and resolvable pointers. What they
cannot see is what this skill is actually made of: a closed grade vocabulary
that only one file defines, four language lanes that must match the floors they
grade against, and a consent model that is prose and therefore one tidy-up away
from being gone.

Each contract here is a claim about content that would still read perfectly if
it broke, which is why it needs a test rather than a reviewer.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

_SKILL = Path(__file__).resolve().parents[3] / "skills" / "toolchain-doctor"
_CAPABILITIES = sorted(_SKILL.glob("capabilities/*/capability.md"))

# Grades are declared as the first column of the vocabulary table, in the one
# file that owns them. The table is anchored by its header rather than by row
# shape: capabilities legitimately carry tables whose first column is a
# backticked lowercase word — every config-location table is one — so a
# row-shaped match would call each of them a grade declaration.
_GRADE_TABLE_HEADER = "| Grade | Means | Example |"
_TABLE_ROW = re.compile(r"^\| `([a-z]+)` \|", re.M)
_FENCE = re.compile(r"```.*?```", re.S)

# Two narrow frames the skill's prose uses to attach a grade to a finding.
# Narrow on purpose: a loose frame sweeps up tool names sitting near the word
# "graded" and then reports them as unregistered vocabulary, which trains
# whoever hits it to widen the allowlist rather than fix the text.
_GRADE_USES = (
    re.compile(r"\bgraded\s+(?:an?\s+)?`([a-z]+)`"),
    re.compile(r"`([a-z]+)`\s+finding"),
)

# The commands the router's consent model promises never to run. Listed here so
# a principle that quietly loses one fails rather than reads the same.
_INSTALL_COMMANDS = (
    "pip install",
    "npm i",
    "cargo install",
    "brew install",
    "rustup component add",
)


def _prose(path: Path) -> str:
    """File text with fenced blocks removed — a template's contents illustrate a
    file the user writes, and are not the skill speaking."""
    return _FENCE.sub("", path.read_text(encoding="utf-8"))


def _registered_grades() -> set[str]:
    text = _prose(_SKILL / "references" / "diagnosis-grading.md")
    header = text.find(_GRADE_TABLE_HEADER)
    assert header != -1, f"no {_GRADE_TABLE_HEADER!r} — has the vocabulary table moved?"
    # Rows run to the blank line that closes the table; anything after it is
    # prose about the grades rather than more of them.
    table = text[header:].split("\n\n", 1)[0]
    grades = set(_TABLE_ROW.findall(table))
    assert grades, "the vocabulary table declares no grades"
    return grades


def test_every_capability_reaches_the_three_contracts_it_runs_on() -> None:
    """A capability that loses one of these does not fail; it improvises.

    Without the mode contract it decides for itself what scan may read; without
    the floors it grades against its own recollection of them; without the
    grading vocabulary it invents a severity, which is precisely the posture
    this skill promises not to take.
    """
    required = (
        "../../references/modes.md",
        "../../references/tooling-floors.md",
        "../../references/diagnosis-grading.md",
    )
    missing = [
        f"{path.parent.name} -> {ref}"
        for path in _CAPABILITIES
        for ref in required
        if ref not in path.read_text(encoding="utf-8")
    ]
    assert not missing, "capabilities not wired to a shared contract:\n" + "\n".join(
        missing
    )


def test_no_capability_defines_a_grade_of_its_own() -> None:
    """One home for the vocabulary. A capability that grows its own grade table
    is how two files start disagreeing about what `wiring` means."""
    offenders = [
        path.parent.name
        for path in _CAPABILITIES
        if _GRADE_TABLE_HEADER in _prose(path)
    ]
    assert (
        not offenders
    ), f"{offenders} open a grade table; grades live in references/diagnosis-grading.md"


def test_every_grade_a_capability_assigns_is_registered() -> None:
    """The reverse direction of the registry: a grade used but never declared."""
    registered = _registered_grades()
    used = {
        (path.parent.name, grade)
        for path in _CAPABILITIES
        for frame in _GRADE_USES
        for grade in frame.findall(_prose(path))
    }
    unregistered = sorted(
        f"{where}: `{grade}`" for where, grade in used if grade not in registered
    )
    assert not unregistered, (
        "grades assigned but not declared in references/diagnosis-grading.md:\n"
        + "\n".join(unregistered)
    )
    assert (
        used
    ), "no capability assigns a grade in a recognized frame — check the frames"


@pytest.mark.parametrize("grade", sorted(_registered_grades()))
def test_every_registered_grade_is_used(grade: str) -> None:
    """The forward direction: vocabulary declared and never applied.

    A grade nothing assigns is a promise the reports never keep, and it reads as
    coverage — a maintainer scanning the table has no way to tell which rows the
    skill can actually produce.
    """
    marker = f"`{grade}`"
    users = [path.parent.name for path in _CAPABILITIES if marker in _prose(path)]
    assert users, f"`{grade}` is declared but no capability ever assigns it"


def test_the_language_lanes_match_the_floors_they_grade_against() -> None:
    """A lane with no floor grades against nothing; a floor with no lane is
    unreachable. Either way the skill claims a language it cannot serve."""
    lanes = {path.parent.name for path in _CAPABILITIES}
    floors = set(
        re.findall(
            r"^## ([a-z]+)$",
            (_SKILL / "references" / "tooling-floors.md").read_text(encoding="utf-8"),
            re.M,
        )
    )
    assert lanes == floors, (
        f"lanes without a floor: {sorted(lanes - floors) or '—'}; "
        f"floors without a lane: {sorted(floors - lanes) or '—'}"
    )


def test_the_consent_model_still_names_what_it_forbids() -> None:
    """The never-installs principle is the skill's whole ethical claim, and it is
    a paragraph of prose. Enumerating the commands is what makes it checkable at
    all — a principle that says "never installs anything" and names nothing
    survives any edit, including the one that hollows it out."""
    router = _prose(_SKILL / "SKILL.md")
    missing = [command for command in _INSTALL_COMMANDS if command not in router]
    assert not missing, f"the never-installs principle no longer names: {missing}"


@pytest.mark.parametrize("capability", _CAPABILITIES, ids=lambda p: p.parent.name)
def test_no_capability_instructs_an_install(capability: Path) -> None:
    """Fenced templates may show an install command — a CI step the user applies
    is the user installing, which is the whole point of prescribing rather than
    performing. The capability's own prose may not, because prose is the skill
    telling itself what to do.
    """
    prose = _prose(capability)
    found = [command for command in _INSTALL_COMMANDS if command in prose]
    assert not found, (
        f"{capability.parent.name} instructs {found} outside a template fence; "
        "the skill prescribes installs, it does not perform them"
    )
