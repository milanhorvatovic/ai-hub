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


def _consent_text(path: Path) -> str:
    """What the skill says in its own voice, for the consent contract.

    Fences are exempt in scaffold templates and nowhere else. There, a fenced
    install is a CI step the user applies — the whole point of prescribing
    rather than performing. In the router, a capability, or a shared reference,
    a fence is still the skill talking, so exempting it everywhere let a fenced
    order sit in a loaded instruction with the guard green.
    """
    text = path.read_text(encoding="utf-8")
    return _FENCE.sub("", text) if path.name == "scaffold-templates.md" else text


# An imperative reaching for one of the forbidden commands. Backticks are
# optional in the pattern on purpose: markdown normally code-formats a command,
# so "Run `pip install foo` first" is the *most* natural way to write the
# violation, and a check that ignored inline code would be blind to exactly it.
# What separates an instruction from a citation is the imperative in front,
# not the formatting around it.
_IMPERATIVE = r"\b(?:run|execute|invoke|call|then|install|use|add)\b"
# The span between the verb and the command. A sentence ends the reach; a line
# break does not, because "Run this command:\n`pip install foo`" is one
# instruction wearing two lines.
_REACH = r"[^.]{0,40}?"
# A prohibition carries the same verb as an order and means the opposite.
_NEGATION = re.compile(r"\b(?:never|not|no|forbid(?:s|den)?|without|avoid)\b", re.IGNORECASE)
# ...unless the negation belongs to a condition rather than to the verb. "If
# ruff is not installed, run pip install ruff" negates the state and orders the
# command, so the negation must not be read as a prohibition there. Anchoring
# the negation to the verb instead was tried and fails the router's own list,
# where the single "No" governs eleven commands across one long sentence.
_CONDITIONAL = re.compile(r"\b(?:if|unless|when|where|whenever)\b", re.IGNORECASE)


def _instructs(prose: str, command: str) -> bool:
    """True when the prose tells someone to run `command`, rather than citing it.

    A capability has to name the commands it detects — an unconstrained
    `pip install` in a CI step is the evidence behind a whole finding — so a
    flat search for the command reports every citation as a violation. The
    discriminator is the imperative, minus the two ways an imperative appears
    without being one: a prohibition ("never run …") carries the same verb and
    means the opposite, and an order can span the line break between "Run this
    command:" and the command itself.

    This stays a heuristic over prose, and it has been wrong three times now —
    once too broad, once blind to code formatting, once to both of these. It
    catches the shapes below and no more; treat a green run as "none of these
    spellings appear", not as proof the skill never tells itself to install.
    """
    for match in re.finditer(_IMPERATIVE + _REACH + r"`?" + re.escape(command), prose, re.IGNORECASE):
        verb_start = match.start()
        sentence_start = prose.rfind(".", 0, verb_start) + 1
        clause = prose[sentence_start:verb_start]
        negation = _NEGATION.search(clause)
        conditional = _CONDITIONAL.search(clause)
        # A negation governs the verb unless a condition opened before it, in
        # which case the negation belongs to the condition.
        negated = negation is not None and not (
            conditional is not None and conditional.start() < negation.start()
        )
        if not negated:
            return True
    return False


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
    ("typescript", "typescript-eslint", "a scaffolded linter must parse the language"),
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


@pytest.mark.parametrize("doc", _ALL_SKILL_DOCS, ids=lambda p: str(p.relative_to(_SKILL)))
def test_no_shipped_file_instructs_an_install(doc: Path) -> None:
    """Fenced templates may show an install command — a CI step the user applies
    is the user installing, which is the whole point of prescribing rather than
    performing. Citations may appear in prose, because naming what the audit
    detects is the capability's job. What may not appear is an imperative: the
    skill telling itself to run one.

    The discriminator is the verb, not the backticks. An earlier version of this
    test stripped inline code before searching, which cleared the citations and
    also cleared "Run `pip install foo` first" — the most natural spelling of
    the violation, since markdown code-formats commands by default.

    Scope is every shipped markdown file, not the capabilities alone. The router
    and the shared references are loaded instructions too, so a capability-only
    check would have been green with an imperative sitting in either.
    """
    prose = _consent_text(doc)
    found = [command for command in _INSTALL_COMMANDS if _instructs(prose, command)]
    assert not found, (
        f"{doc.relative_to(_SKILL)} instructs {found} outside a template fence; "
        "the skill prescribes installs, it does not perform them"
    )


def test_the_consent_check_can_tell_an_order_from_a_citation() -> None:
    """Both halves of the discriminator, asserted directly.

    Each failure mode of this check looks like a passing test: too loose and
    every capability trips on the commands it exists to detect, too tight and
    the check reports nothing it was written to catch. Neither shows up in a
    green run, so both are exercised here.
    """
    assert _instructs("Run `pip install foo` first.", "pip install")
    assert _instructs("Then execute pip install ruff before the scan.", "pip install")
    # The verbs that read least like orders are the ones a violation reaches
    # for: nobody writes "run cargo install", they write "install it with".
    assert _instructs("Install it with `pip install ruff`.", "pip install")
    assert _instructs("Use `cargo install cargo-deny` to get it.", "cargo install")
    assert _instructs("Add it with `brew install shfmt` before scanning.", "brew install")
    assert not _instructs(
        "A CI step reading `pip install ruff` is a `floating` finding.", "pip install"
    )
    assert not _instructs("The floor forbids `pip install` into a global interpreter.", "pip install")
    assert not _instructs(
        "Where the project declares one and CI reaches for a bare `pip install` instead.",
        "pip install",
    )
    # An order can span the line break between the lead-in and the command.
    assert _instructs("Run this command:\n`pip install ruff`.", "pip install")
    # A prohibition carries the same verb and means the opposite; flagging it
    # would reject the clearest way a capability can state the rule.
    assert not _instructs("Never run `pip install` on the user's behalf.", "pip install")
    assert not _instructs("The skill does not run `pip install` for them.", "pip install")
    # A negation inside a condition negates the condition, not the order.
    assert _instructs("If ruff is not installed, run `pip install ruff`.", "pip install")
    assert _instructs("When the lock is absent, use `uv add ruff` instead.", "uv add")
