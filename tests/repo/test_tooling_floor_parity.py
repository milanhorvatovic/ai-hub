"""Hold the two skills that state a tooling floor to the same floor.

Skills ship standalone — `npx skills add` installs one directory — so a skill
that diagnoses a repository against a tooling floor cannot reference the
rulebook that states one; it has to carry its own copy. Distribution forces the
duplication, and duplication drifts: the rulebook gains a formatter, the doctor
keeps grading against the old set, and each file reads perfectly well on its
own while they disagree about what a project needs.

This turns the forced copy into a pinned contract. Both sides are *extracted*
rather than listed here, so the test is a comparison and not a third copy that
can drift with the other two: the doctor's floors come from its floor tables,
the rulebook's from the section of each language capability that states the
floor, and every direction of disagreement fails.

Extraction rejects the things a floor's prose backticks that are not tools —
config filenames, compiler options, a shell directive — by shape rather than by
name, so a genuinely new tool on either side has nowhere to hide.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
_FLOORS = (
    _REPO_ROOT / "skills" / "toolchain-doctor" / "references" / "tooling-floors.md"
)
_RULEBOOK = _REPO_ROOT / "skills" / "coding-principles" / "capabilities"

# The heading that opens each language's floor in the rulebook. bash states its
# tooling under a different heading than the other three, which is a fact about
# that capability's layout rather than a naming inconsistency worth fixing.
_FLOOR_HEADINGS = {
    "python": "## Floor",
    "typescript": "## Floor",
    "rust": "## Floor",
    "bash": "## Tooling",
}

# Backticked spans that are not tools, kept as an explicit list because their
# shape alone does not give them away. `pip install` is named by the floor to
# forbid it; `python_requires` is a manifest key the floor reads.
_NOT_TOOLS = frozenset({"pip install", "python_requires"})

_BACKTICKED = re.compile(r"`([^`]+)`")
# A config file, a JSON setting, a shell directive, or a path: every one of them
# carries a character a tool name does not.
_NOT_A_TOOL_NAME = re.compile(r"[./\"':=#]")
# `noUncheckedIndexedAccess` and friends — compiler options, not tools.
_CAMEL_CASE = re.compile(r"[a-z][a-zA-Z]*[A-Z]")
# Flags start at the first ` -`, so `cargo clippy -- -D warnings` is the same
# tool as `cargo clippy` and `shfmt -i 2 -ci` the same tool as `shfmt`.
_FLAGS = re.compile(r"\s+-.*$")


def _tool_names(spans: list[str]) -> set[str]:
    """The tool names among a set of backticked spans, normalized past flags.

    Flags come off before the rejection filters run, not after: `tsc --noEmit`
    carries a camelCase flag, and rejecting on the raw span would drop the tool
    for the shape of the option beside it.
    """
    tools = set()
    for span in spans:
        # Case survives the filters and is folded only at the end: the
        # camelCase test is the filter that spots a compiler option, and
        # lowercasing first would leave it nothing to see.
        name = _FLAGS.sub("", span).strip()
        if not name or name.lower() in _NOT_TOOLS:
            continue
        if _NOT_A_TOOL_NAME.search(name) or _CAMEL_CASE.search(name):
            continue
        tools.add(name.lower())
    return tools


def _doctor_floor(language: str) -> set[str]:
    """The tools the doctor's floor table names for one language."""
    text = _FLOORS.read_text(encoding="utf-8")
    section = re.search(rf"^## {language}$(.*?)(?=^## |\Z)", text, re.S | re.M)
    assert section, f"tooling-floors.md has no `## {language}` section"

    spans: list[str] = []
    for line in section.group(1).splitlines():
        # The table's first column is the Tool column; the header and the
        # separator carry no backticks, so they fall out on their own. A row
        # offering equivalents spells them `a` _or_ `b`, and both are the floor.
        if line.startswith("| `"):
            spans.extend(_BACKTICKED.findall(line.split("|")[1]))
    assert spans, f"no floor table rows found under `## {language}`"
    return _tool_names(spans)


def _rulebook_floor(language: str) -> set[str]:
    """The tools the rulebook's floor section names for one language."""
    capability = _RULEBOOK / language / "capability.md"
    text = capability.read_text(encoding="utf-8")
    heading = _FLOOR_HEADINGS[language]
    section = re.search(rf"^{re.escape(heading)}$(.*?)(?=^## |\Z)", text, re.S | re.M)
    assert section, f"{capability.name} has no `{heading}` section"
    return _tool_names(_BACKTICKED.findall(section.group(1)))


@pytest.mark.parametrize("language", sorted(_FLOOR_HEADINGS))
def test_both_skills_state_the_same_floor(language: str) -> None:
    """Neither side may move a floor alone.

    Read the two directions separately when this fails: a tool only the doctor
    names is a floor it invented, and a tool only the rulebook names is one the
    doctor will never grade a repository against.
    """
    doctor = _doctor_floor(language)
    rulebook = _rulebook_floor(language)

    assert doctor == rulebook, (
        f"the {language} floor disagrees between the two skills.\n"
        f"  only the doctor names: {sorted(doctor - rulebook) or '—'}\n"
        f"  only the rulebook names: {sorted(rulebook - doctor) or '—'}\n"
        "Both files state the same floor; move them together."
    )


@pytest.mark.parametrize("language", sorted(_FLOOR_HEADINGS))
def test_the_floor_is_not_empty(language: str) -> None:
    """An extraction that finds nothing agrees with an extraction that finds
    nothing, so the comparison above passes loudest exactly when it has stopped
    reading either file. This is what stands between that and a green suite."""
    assert _doctor_floor(
        language
    ), f"extracted no tools from the doctor's {language} floor"
    assert _rulebook_floor(
        language
    ), f"extracted no tools from the rulebook's {language} floor"


def test_the_doctor_covers_every_language_the_rulebook_floors() -> None:
    """The doctor's language set is the rulebook's, so a fifth language added to
    one is a visible gap rather than a silent one — a repository the doctor
    cannot audit against a floor the fleet already states."""
    text = _FLOORS.read_text(encoding="utf-8")
    doctored = set(re.findall(r"^## ([a-z]+)$", text, re.M))
    floored = {
        path.parent.name
        for path in _RULEBOOK.glob("*/capability.md")
        if re.search(r"^## (Floor|Tooling)$", path.read_text(encoding="utf-8"), re.M)
    }
    assert doctored == floored, (
        "the two skills cover different languages.\n"
        f"  only the doctor: {sorted(doctored - floored) or '—'}\n"
        f"  only the rulebook: {sorted(floored - doctored) or '—'}"
    )


def test_the_extractor_rejects_what_is_not_a_tool() -> None:
    """The filters are the load-bearing part: without them the comparison drowns
    in config filenames and compiler options, and with them too aggressive it
    quietly drops a real tool. Both failure modes look like a passing test, so
    the shapes are asserted directly rather than inferred from a green run."""
    rejected = [
        "pyproject.toml",
        '"strict": true',
        "noUncheckedIndexedAccess",
        "pip install",
    ]
    assert (
        _tool_names(rejected) == set()
    ), f"filters let through: {_tool_names(rejected)}"

    kept = ["ruff", "cargo clippy -- -D warnings", "shfmt -i 2 -ci", "tsc --noEmit"]
    assert _tool_names(kept) == {"ruff", "cargo clippy", "shfmt", "tsc"}
