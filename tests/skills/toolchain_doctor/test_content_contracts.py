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
from collections import Counter
from pathlib import Path

import pytest

_SKILL = Path(__file__).resolve().parents[3] / "skills" / "toolchain-doctor"
_CAPABILITIES = sorted(_SKILL.glob("capabilities/*/capability.md"))
# Every markdown file the skill ships. The consent contract is a promise about
# the whole skill, and the router and shared references are loaded instructions
# exactly as capabilities are — an imperative dropped into one of those would
# have left a capability-only check green.
_ALL_SKILL_DOCS = sorted(_SKILL.rglob("*.md"))

# Grades are declared as the first column of the vocabulary table, in the one
# file that owns them. The table is anchored by its header rather than by row
# shape: capabilities legitimately carry tables whose first column is a
# backticked lowercase word — every config-location table is one — so a
# row-shaped match would call each of them a grade declaration.
_GRADE_TABLE_HEADER = "| Grade | Means | Example |"
_TABLE_ROW = re.compile(r"^\| `([a-z]+)` \|", re.M)
_FENCE = re.compile(r"```.*?```", re.S)
_INLINE_CODE = re.compile(r"`[^`\n]*`")

# The frames the skill's prose uses to attach a grade to a finding. Both
# registry directions read through these, so "declared" and "assigned" are the
# same question asked twice — a presence check would pass on a sentence that
# merely names a grade to say something is *not* one, which is a dead entry
# wearing a citation.
#
# Each frame is anchored to a verb or a noun rather than to proximity: a loose
# frame sweeps up the tool names sitting near the word "graded" and reports
# them as unregistered vocabulary, which teaches whoever hits it to widen an
# allowlist instead of fixing the text.
_GRADE_USES = (
    re.compile(r"\bgraded\s+(?:an?\s+)?`([a-z]+)`"),
    re.compile(r"`([a-z]+)`\s+finding"),
    re.compile(r"\bis an?\s+`([a-z]+)`"),
    re.compile(r"\bgrade\s+(?:the\s+\w+(?:\s+\w+)?\s+row\s+)?(?:an?\s+)?`([a-z]+)`"),
)

# The commands the router's consent model promises never to run. Listed here so
# a principle that quietly loses one fails rather than reads the same.
#
# The list covers the package managers this skill actually discusses, because
# the router's promise is about any of them and a detector holding five names
# pins a much smaller promise than the one written. The managers named in the
# floors are the ones a reader is most likely to be told to reach for.
_INSTALL_COMMANDS = (
    "pip install",
    "uv add",
    "poetry add",
    "pipenv install",
    "npm i",
    "pnpm add",
    "yarn add",
    "bun add",
    "cargo install",
    "brew install",
    "rustup component add",
)


def _prose(path: Path) -> str:
    """File text with fenced blocks removed — a template's contents illustrate a
    file the user writes, and are not the skill speaking."""
    return _FENCE.sub("", path.read_text(encoding="utf-8"))


# Every install-or-modify form of every package manager this skill discusses.
# Subcommands rather than manager names: `cargo fmt` and `npm run` invoke checks,
# and forbidding those would flag the tools the floors are built from.
_MANAGER = r"(?:pip|pipx|uv|poetry|pipenv|hatch|npm|pnpm|yarn|bun|cargo|rustup|brew|apt-get)"
# Options sit between a manager and its subcommand more often than the literal
# forms suggest — `pip --require-virtualenv install`, `npm --prefix web install`
# — and a pattern demanding they be adjacent misses every one of those.
_MANAGER_OPTIONS = r"(?:\s+--?[\w-]+(?:[= ]\S+)?)*"
# The subcommands that install or mutate an environment. `check`, `run`, `fmt`,
# and `clippy` are deliberately absent: those are the tools the floors are made
# of, and matching them would flag the skill for naming its own subject.
_INSTALL_SUBCOMMAND = (
    r"(?:install|add|sync|ci|i\b|tool install|env create|component add"
    r"|toolchain install|pip install)"
)
# Not every environment-mutating command is a manager plus a subcommand.
# `pip-sync` is one word, and `corepack enable` provisions a manager rather than
# a package — both are mechanisms this skill names, and neither fits the shape
# above.
_STANDALONE_FORMS = r"(?:pip-sync|pip-compile|corepack enable|corepack prepare)"
_INSTALL_FORMS = re.compile(
    rf"\b(?:{_MANAGER}{_MANAGER_OPTIONS}\s+{_INSTALL_SUBCOMMAND}|{_STANDALONE_FORMS})"
)


# The sites allowed to name one, each with the reason it is there.
#
# An inventory, after five rounds in which a regex trying to tell an order from
# a citation was wrong five different ways: too broad, blind to code formatting,
# blind to line breaks, tripped by a conditional, tripped by a neighbouring
# clause. Every fix passed the tests written for it and failed a shape nobody
# had thought of, which is what using the wrong instrument looks like from the
# inside — each round felt like the last one.
#
# This cannot have a false negative. A new occurrence anywhere fails until it is
# listed, and listing it is the review moment: someone has to say why the skill
# is naming an install command, which is the judgement the regex was pretending
# to make on its own.
# Exact counts, not a set of spellings. Recording only which commands a file
# names lets an allowlisted file gain a second occurrence — a real instruction
# beside the citation that justified listing it — without the tally moving, so
# the promise that "a new occurrence anywhere fails" would have held only for
# new files. The count is what makes it true for new sentences too.
_ALLOWED_CITATIONS: dict[str, dict[str, int]] = {
    # The consent model's own enumeration of what it refuses to run.
    "SKILL.md": {
        "brew install": 1,
        "bun add": 1,
        "cargo install": 1,
        "npm i": 1,
        "pip install": 1,
        "pipenv install": 1,
        "pnpm add": 1,
        "poetry add": 1,
        "rustup component add": 1,
        "uv add": 1,
        "yarn add": 1,
    },
    # Evidence for the unpinned-tool finding and the environment-manager one,
    # plus `pip-compile` naming the header that identifies a locked
    # requirements file in the declaration table.
    "capabilities/python/capability.md": {"pip install": 2, "pip-compile": 1},
    # The counter-example — what the CI step must not do instead of the lock —
    # and `pip-sync` among the managers a fresh runner does not carry.
    "capabilities/python/references/scaffold-templates.md": {
        "pip install": 1,
        "pip-sync": 1,
    },
    # The worked example of a `floating` finding.
    "references/diagnosis-grading.md": {"pip install": 1},
}


def _install_citations(path: Path) -> dict[str, int]:
    """Install forms the file names in the skill's own voice.

    Fences are exempt in scaffold templates and nowhere else: there a fenced
    install is a CI step the user applies, which is the whole point of
    prescribing rather than performing. In the router, a capability, or a shared
    reference, a fence is still the skill talking.
    """
    text = path.read_text(encoding="utf-8")
    body = _FENCE.sub("", text) if path.name == "scaffold-templates.md" else text
    return dict(Counter(_INSTALL_FORMS.findall(body)))


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
    assert not missing, "capabilities not wired to a shared contract:\n" + "\n".join(missing)


def test_no_capability_defines_a_grade_of_its_own() -> None:
    """One home for the vocabulary. A capability that grows its own grade table
    is how two files start disagreeing about what `wiring` means."""
    offenders = [
        path.parent.name for path in _CAPABILITIES if _GRADE_TABLE_HEADER in _prose(path)
    ]
    assert offenders == [], (
        f"{offenders} open a grade table; grades live in references/diagnosis-grading.md"
    )


def test_every_grade_a_capability_assigns_is_registered() -> None:
    """The reverse direction of the registry: a grade used but never declared."""
    registered = _registered_grades()
    used = {
        (path.parent.name, grade)
        for path in _CAPABILITIES
        for grade in _assigned_grades(path)
    }
    unregistered = sorted(
        f"{where}: `{grade}`" for where, grade in used if grade not in registered
    )
    assert not unregistered, (
        "grades assigned but not declared in references/diagnosis-grading.md:\n"
        + "\n".join(unregistered)
    )
    assert used, "no capability assigns a grade in a recognized frame — check the frames"


def _assigned_grades(path: Path) -> set[str]:
    """The grades a capability actually attaches to a finding."""
    prose = _prose(path)
    return {grade for frame in _GRADE_USES for grade in frame.findall(prose)}


@pytest.mark.parametrize("grade", sorted(_registered_grades()))
def test_every_registered_grade_is_used(grade: str) -> None:
    """The forward direction: vocabulary declared and never applied.

    A grade nothing assigns is a promise the reports never keep, and it reads as
    coverage — a maintainer scanning the table has no way to tell which rows the
    skill can actually produce.

    Assignment, not mention. Asking only whether the token appears lets a
    sentence that names a grade to rule it out — "that is not a `gap`" — stand
    in for one that produces it, so a genuinely dead entry keeps its citation
    and the invariant this test claims to hold quietly stops holding.
    """
    users = [path.parent.name for path in _CAPABILITIES if grade in _assigned_grades(path)]
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


# Shapes a capability's audit calls out, which its own templates must therefore
# not prescribe. Each entry pairs the shape with a phrase from the audit bullet
# that flags it, so the pin cannot drift into forbidding something the skill
# does not actually grade — the anchor is asserted alongside the shape.
#
# A pin has to name a shape that is wrong on its own, not one that is wrong in
# some contexts. `npx <tool>` was pinned here and should not have been: it
# resolves a declared dependency's own binary, so the command is only a defect
# when the package is undeclared, and the blanket ban would have rejected the
# `npx --no-install` form this repository itself relies on. A conditional rule
# belongs in the capability's prose, where the condition can be stated.
_SELF_CONTRADICTIONS = (
    ("rust", "cargo check", "`cargo check` standing in for `clippy`"),
    ("python", "pip install", "A CI job that installs past the environment manager"),
)


@pytest.mark.parametrize(
    ("language", "shape", "anchor"), _SELF_CONTRADICTIONS, ids=lambda v: str(v)[:24]
)
def test_no_template_prescribes_what_its_own_audit_flags(
    language: str, shape: str, anchor: str
) -> None:
    """The doctor has to agree with itself.

    A scaffold exists to close a finding, so a template that hands the user a
    shape the same capability grades as a defect leaves the repository failing
    an audit it just passed — and the contradiction is invisible from either
    file alone, because each one reads as sensible advice. This caught a real
    one: the typescript CI template prescribed `npx` invocations on the same
    day the capability started grading them as unpinned.
    """
    capability = _SKILL / "capabilities" / language / "capability.md"
    assert anchor in capability.read_text(encoding="utf-8"), (
        f"{language}'s audit no longer flags {shape!r} — drop this pin or "
        "restore the finding, but do not leave a template pinned to nothing"
    )

    templates = _SKILL / "capabilities" / language / "references" / "scaffold-templates.md"
    fenced = "\n".join(_FENCE.findall(templates.read_text(encoding="utf-8")))
    assert shape not in fenced, (
        f"{language}'s templates prescribe {shape!r}, which its own audit grades "
        "as a finding — a scaffolded repo would not re-audit clean"
    )


# The other half of template drift: not a shape that must be absent, but one
# that must be present. Each entry is a defect this suite has already let
# through once — the eslint route shipping without a TypeScript parser, the
# editorconfig covering one of the two extensions its inventory collects — and
# each names the capability text that makes it required, so the pin cannot
# outlive the rule.
_TEMPLATE_MUST_CARRY = (
    ("typescript", "tseslint.config(", "a scaffolded linter must parse the language"),
    ("bash", "[*.{sh,bash}]", "a scaffolded policy covers every path the inventory collects"),
)


@pytest.mark.parametrize(
    ("language", "required", "anchor"), _TEMPLATE_MUST_CARRY, ids=lambda v: str(v)[:24]
)
def test_the_templates_still_carry_what_their_capability_requires(
    language: str, required: str, anchor: str
) -> None:
    """A scaffold can fail its audit by omission as easily as by commission.

    The forbidden-shape pins next to this one only catch a template that adds
    something wrong. These catch one that drops something needed, which is the
    direction two real defects took: an eslint config with no TypeScript parser
    lints almost none of a TypeScript project while appearing to satisfy the
    floor, and an editorconfig keyed to a single extension leaves half the
    inventory on the formatter's defaults.
    """
    capability = _SKILL / "capabilities" / language / "capability.md"
    templates = _SKILL / "capabilities" / language / "references" / "scaffold-templates.md"
    assert anchor in capability.read_text(encoding="utf-8"), (
        f"{language}'s capability no longer states the rule behind {required!r} — "
        "drop this pin or restore the rule, but do not pin a template to nothing"
    )
    fenced = "\n".join(_FENCE.findall(templates.read_text(encoding="utf-8")))
    assert required in fenced, (
        f"{language}'s templates no longer carry {required!r} in a fence, which "
        "its own capability requires — a scaffolded repo would not re-audit clean. "
        "Prose mentioning it is not the scaffold; only the fenced content is what "
        "a user receives."
    )


@pytest.mark.parametrize("doc", _ALL_SKILL_DOCS, ids=lambda p: p.relative_to(_SKILL).as_posix())
def test_only_inventoried_files_name_an_install_command(doc: Path) -> None:
    """The consent model, pinned by inventory rather than by reading intent.

    The skill promises it never runs a package manager. A file naming one is
    either citing it — as evidence, as a counter-example, or as the list of what
    is refused — or instructing it, and nothing pattern-matching over prose has
    reliably told those apart. So every naming site is listed and an unlisted
    one fails: the check is exact, and the judgement moves to whoever adds the
    citation.
    """
    # `as_posix()`, not `str()`: on Windows the latter yields backslashes and
    # every nested key in the inventory misses, which is how this landed red on
    # two runners while passing locally.
    relative = doc.relative_to(_SKILL).as_posix()
    found = _install_citations(doc)
    expected = _ALLOWED_CITATIONS.get(relative, {})
    assert found == expected, (
        f"{relative} names {found} outside a template fence; the inventory expects "
        f"{expected or 'none'}. A file citing an install command is listed with the "
        "exact forms and counts it carries — if the skill is citing one more, record "
        "it and say why; if it is instructing one, the contract is breaking."
    )


def test_the_citation_inventory_describes_this_tree() -> None:
    """An inventory that outlives its citations stops being one — a listed file
    that no longer names an install form is a standing permission nobody would
    notice granting."""
    stale = [name for name in _ALLOWED_CITATIONS if not _install_citations(_SKILL / name)]
    assert not stale, f"inventory lists files that no longer cite an install form: {stale}"

    # The keys are compared against `as_posix()` output, so a backslash in one
    # can only ever miss. Pinning the spelling here fails on every platform
    # rather than only on the runners that use the other separator.
    windows_style = [name for name in _ALLOWED_CITATIONS if "\\" in name]
    assert not windows_style, (
        f"inventory keys must be posix-form paths; these carry backslashes: {windows_style}"
    )


def test_the_install_detector_reads_forms_not_tool_names() -> None:
    """Both halves of the pattern, asserted directly.

    Too narrow and the guard misses `uv sync` while catching `uv add`; too broad
    and it flags `cargo fmt`, which is a floor tool rather than an install.
    """
    assert _INSTALL_FORMS.search("run `uv sync` first")
    assert _INSTALL_FORMS.search("then `npm ci`")
    assert _INSTALL_FORMS.search("`poetry install`")
    # Options between the manager and the subcommand are the shape a literal
    # alternation misses, and the one an instruction most plausibly carries.
    assert _INSTALL_FORMS.search("`pip --require-virtualenv install ruff`")
    assert _INSTALL_FORMS.search("`npm --prefix web install`")
    assert _INSTALL_FORMS.search("`uv tool install ruff`")
    # Shapes that are not manager-plus-subcommand at all.
    assert _INSTALL_FORMS.search("run `pip-sync` in CI")
    assert _INSTALL_FORMS.search("`corepack enable` first")
    assert not _INSTALL_FORMS.search("`cargo fmt --check`")
    assert not _INSTALL_FORMS.search("`npm run lint`")
    assert not _INSTALL_FORMS.search("`uv run ruff`")
    assert not _INSTALL_FORMS.search("`cargo check`")
    assert not _INSTALL_FORMS.search("`poetry run pytest`")
