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
floor.

The two comparisons have different reach, deliberately. Tool identity is pinned
both ways — a name added or dropped on either side fails — while the
requirements attached to a shared tool are pinned one way: every flag the
rulebook asks for must survive on the doctor's side, and the doctor adding one
of its own does not fail. It legitimately asks for check-mode flags the rulebook
has no reason to state, so a superset is the safe direction to differ in, and
the guarantee that matters is that the graded bar can never fall below the
stated one.

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

# The heading that opens each language's floor in the rulebook, discovered
# rather than listed. bash states its tooling under a different heading than the
# other three, which is a fact about that capability's layout rather than a
# naming inconsistency worth fixing — so the discovery accepts either.
#
# Listing them would quietly exclude a fifth language from every comparison
# below: the set test at the bottom would go green the moment both skills gained
# it, while its tools and flags were never once compared. Parametrizing over
# what is on disk is what makes a synchronized addition arrive fully checked.
_FLOOR_HEADING = re.compile(r"^## (Floor|Tooling)$", re.M)


def _discover_floor_headings() -> dict[str, str]:
    found = {}
    for path in sorted(_RULEBOOK.glob("*/capability.md")):
        match = _FLOOR_HEADING.search(path.read_text(encoding="utf-8"))
        if match:
            found[path.parent.name] = f"## {match.group(1)}"
    assert found, "no floor headings found in the rulebook — has its layout moved?"
    return found


_FLOOR_HEADINGS = _discover_floor_headings()

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


# A flag is what turns a tool name into a requirement: `clippy` says which
# binary, `--all-targets -- -D warnings` says what the floor actually asks of
# it. Comparing names alone lets that half drift on either side while both
# sets stay identical, which is the gap this pair of tests closes.
_FLAG = re.compile(r"^--?[A-Za-z][\w-]*$")
# A flag's argument carries the requirement as often as the flag does: `-D`
# alone is "deny something", and only `-D warnings` is the floor. Paths and the
# `--` separator are not arguments, so they never attach.
_ARGUMENT = re.compile(r"^[A-Za-z0-9][\w.=-]*$")
# A command word is the tool or one of its subcommands — `cargo`, `clippy`,
# `ruff`, `check`, `format`. It is what a flag is qualified by, so that two
# subcommands of one tool keep their requirements apart.
_COMMAND_WORD = re.compile(r"^[A-Za-z][\w-]*$")


def _role(command: str) -> str:
    """The tool-and-subcommand prefix of an invocation, before its first flag.

    `ruff format --check .` and `ruff check .` share the tool name the floor
    tables print and differ only here, so a flag has to be qualified by this
    prefix or the two subcommands' requirements merge under `ruff` — and a floor
    that moved `--check` from `format` to `check` would read as unchanged while
    it had quietly stopped checking formatting. Cargo's tools already carry the
    subcommand in the name the tables use (`cargo clippy`, `cargo fmt`), so there
    this reproduces that name; `ruff` is the case that needs it.
    """
    words = []
    for token in command.split():
        if not _COMMAND_WORD.match(token):
            break
        words.append(token)
    return " ".join(words)


def _requirements(command: str) -> set[str]:
    """The flags of one invocation, each carrying its argument where it has one."""
    tokens = command.split()
    out: set[str] = set()
    for index, token in enumerate(tokens):
        if not _FLAG.match(token):
            continue
        following = tokens[index + 1] if index + 1 < len(tokens) else ""
        takes_argument = (
            bool(following)
            and not _FLAG.match(following)
            and bool(_ARGUMENT.match(following))
        )
        out.add(f"{token} {following}" if takes_argument else token)
    return out


def _flags_for(text: str, tool: str) -> set[str]:
    """Every flag the text attaches to `tool` in the span it is given.

    The two sides are given different spans, and that asymmetry is the point.
    The rulebook's is its whole floor section, unioned: it states requirements in
    prose and quoting a weak form there does not weaken the bar. The doctor's is
    its floor table alone, because that is where its requirements live — a flag
    deleted from the table would otherwise survive in the paragraph warning
    against deleting it, and the comparison would pass while the graded bar had
    dropped. That direction is the one this whole check exists for.

    Each flag is returned qualified by its invocation's role — `ruff format:
    --check`, not a bare `--check` filed under `ruff` — so a requirement that
    moves between a tool's subcommands is a difference the set comparison sees
    rather than one it flattens away.
    """
    flags: set[str] = set()
    for span in _BACKTICKED.findall(text):
        for part in span.split("&&"):
            part = part.strip()
            if part.startswith(tool):
                role = _role(part)
                flags.update(f"{role}: {flag}" for flag in _requirements(part))
    return flags


def _rulebook_text(language: str) -> str:
    """The rulebook's floor plus the verification commands that realize it."""
    capability = (_RULEBOOK / language / "capability.md").read_text(encoding="utf-8")
    heading = _FLOOR_HEADINGS[language]
    floor = re.search(
        rf"^{re.escape(heading)}$(.*?)(?=^## |\Z)", capability, re.S | re.M
    )
    verification = re.search(
        r"^## Verification$(.*?)(?=^## |\Z)", capability, re.S | re.M
    )
    assert floor, f"{language}: no `{heading}` section"
    return floor.group(1) + (verification.group(1) if verification else "")


def _doctor_text(language: str) -> str:
    """The doctor's floor **table** for a language, not the prose around it.

    Only the table states requirements; the paragraphs beside it explain them,
    and they do that partly by quoting the weak forms — `cargo check` where
    clippy belongs, clippy without `--all-targets`. Unioning flags across the
    whole section would let a requirement be deleted from the table and survive
    in the counter-example that warns against dropping it, which is the one
    direction this comparison exists to catch.
    """
    text = _FLOORS.read_text(encoding="utf-8")
    section = re.search(rf"^## {language}$(.*?)(?=^## |\Z)", text, re.S | re.M)
    assert section, f"tooling-floors.md has no `## {language}` section"
    rows = [line for line in section.group(1).splitlines() if line.startswith("| `")]
    assert rows, f"no floor table rows under `## {language}`"
    return "\n".join(rows)


@pytest.mark.parametrize("language", sorted(_FLOOR_HEADINGS))
def test_the_doctor_never_asks_less_of_a_tool_than_the_rulebook(language: str) -> None:
    """The requirements, not just the names.

    `cargo clippy` satisfying the floor and `cargo clippy --all-targets -- -D
    warnings` satisfying it are different bars, and the tool-name comparison
    above cannot tell them apart — both sides would keep an identical set while
    the doctor quietly graded repositories against a weaker rule than the fleet
    states. So every flag the rulebook attaches to a shared tool must still be
    attached on the doctor's side.

    One-directional, and deliberately so. The doctor is allowed to be more
    specific — it supplies `shfmt -d` for a check-mode run and `prettier
    --check` where the rulebook names the tool without an invocation — so a
    superset passes. What that does not catch is the rulebook weakening on its
    own; the doctor then grades against the stricter of the two, which is the
    safe direction to fail in and is worth knowing rather than assuming.
    """
    rulebook_text, doctor_text = _rulebook_text(language), _doctor_text(language)
    dropped: list[str] = []
    for tool in sorted(_doctor_floor(language) & _rulebook_floor(language)):
        missing = _flags_for(rulebook_text, tool) - _flags_for(doctor_text, tool)
        if missing:
            dropped.append(f"{tool}: {sorted(missing)}")
    assert not dropped, (
        f"the doctor's {language} floor drops requirements the rulebook states:\n"
        + "\n".join(dropped)
    )


def test_the_flag_reader_sees_what_it_claims_to() -> None:
    """A flag reader that silently returns nothing agrees with every floor.

    The superset check passes loudest when extraction has stopped working, so
    the reader is exercised against a known invocation rather than trusted
    because the suite is green.
    """
    sample = "run `cargo clippy --all-targets -- -D warnings` and `cargo fmt --check`"
    assert _flags_for(sample, "cargo clippy") == {
        "cargo clippy: --all-targets",
        "cargo clippy: -D warnings",
    }
    assert _flags_for(sample, "cargo fmt") == {"cargo fmt: --check"}
    assert _flags_for(sample, "shellcheck") == set()

    # The argument is half the requirement: a bare `-D` matches any deny, so
    # reading the flag alone would let the floor's `warnings` become anything.
    assert _flags_for("`cargo clippy -- -D deprecated`", "cargo clippy") == {
        "cargo clippy: -D deprecated"
    }
    # A path is not an argument, or `-ci .` and `-ci` would read as different
    # requirements and two sides stating the same floor would disagree.
    assert _flags_for("`shfmt -i 2 -ci .`", "shfmt") == {"shfmt: -i 2", "shfmt: -ci"}

    # A flag on the wrong subcommand no longer hides. `ruff` is one tool with two
    # subcommands, so `--check` under `ruff format` and `--check` under `ruff
    # check` are different requirements; the old flatten-under-`ruff` reading
    # made both `{--check}` and would have passed a floor that moved formatting's
    # check onto the lint subcommand and stopped checking format at all.
    assert _flags_for("`ruff format --check .`", "ruff") == {"ruff format: --check"}
    assert _flags_for("`ruff check --check .`", "ruff") == {"ruff check: --check"}


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
