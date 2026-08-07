"""Wrap-convention contract tests for the commit-message capability.

The body-wrap detection was documented as a rule, but nothing forced it to run
and nothing in the output exposed whether it had — so an agent under habit
pressure could hard-wrap a body in a repo with no hard-wrap convention. The
first four tests pin the three composing tightenings that close the WRITE half:
a mandatory Step 0 pre-flight that runs the wrap-detection recipe, a
Detected-conventions preamble on every WRITE proposal, and a named anti-pattern
for skipping the check. The recipe is read from its single source of truth
(format-body.md) and asserted inlined byte-identically into the pre-flight.

The rest pin the REVIEW half, which stayed open a lifecycle step longer: the
detection had a pre-flight and a preamble but no verdict, so a body wrapped
against a flowing-paragraph convention passed review as COMPLIANT — `body-wrap`
grades only the opposite direction and the schema's enum correctly rejects any
id a capability invents on the spot. `hard-wrapped-paragraph` closes that, and
these tests hold its description to what the repo's own gate actually enforces.
"""

from __future__ import annotations

import importlib.util
import re
from pathlib import Path

import pytest

# A backtick-delimited inline code span.
_BACKTICK_SPAN = re.compile(r"`([^`]+)`")

_REPO_ROOT = Path(__file__).resolve().parents[3]
_LINTER = _REPO_ROOT / ".github" / "scripts" / "lint_commit_message.py"

# The four exemptions the rule carries, each as (label for failure messages,
# phrase the Pattern paragraph must contain, a body of that shape). The bodies
# are probes run through the repo's own commit-style linter — the enforcement
# side of the convention this catalog entry describes.
#
# Each phrase is unique to its own exemption rather than a bare keyword: the
# list exemption is spelled "bullet lists together with their indented
# continuations", so searching for "indented" matched it and let the 4-space
# exemption be deleted with this test still green. Mutation found that; the
# fix is that no phrase may be a substring of another exemption's wording.
_EXEMPTIONS = (
    ("fenced block", "fenced", "```\nwrapped inside\na fence\n```"),
    ("tab/4-space indented block", "4-space", "    wrapped inside\n    a four-space block"),
    ("list continuation", "bullet list", "- item one\n  continues the item"),
    ("trailer block", "trailer block", "Refs #1\nCloses #2"),
)

# Continues the previous line with a 1-3 space indent, which is not a block —
# the carve-out that stops lightly indented prose dodging the rule.
_LIGHT_INDENT_BODY = "One source line of prose,\n  continued on the next"
_WRAPPED_BODY = "One source line of prose,\ncontinued on the next"


def _recipe_spans(text: str) -> list[str]:
    """Backticked `git log … | head …` spans — the wrap-detection recipe form."""
    return [
        s
        for s in _BACKTICK_SPAN.findall(text)
        if s.startswith("git log") and "| head" in s
    ]


@pytest.fixture(scope="session")
def commit_message_md(capabilities_dir: Path) -> str:
    path = capabilities_dir / "commit-message" / "capability.md"
    assert path.is_file(), "commit-message/capability.md not found"
    return path.read_text(encoding="utf-8")


@pytest.fixture(scope="session")
def detection_recipe(references_dir: Path) -> str:
    """The canonical wrap-detection recipe, read from its single source of truth
    (format-body.md) instead of duplicated here, so the SSOT claim stays true."""
    spans = _recipe_spans(
        (references_dir / "format-body.md").read_text(encoding="utf-8")
    )
    assert len(spans) == 1, (
        "expected exactly one 'git log … | head …' recipe span in "
        f"format-body.md, found {len(spans)}: {spans!r}"
    )
    return spans[0]


def _section(text: str, heading: str) -> str:
    """Return the body of a `## <heading>` section, up to the next `## `."""
    assert heading in text, f"section {heading!r} not found"
    return text.split(heading, 1)[1].split("\n## ", 1)[0]


def test_write_mode_has_preflight_detection_step(
    commit_message_md: str, detection_recipe: str
) -> None:
    """WRITE mode must open with a Step 0 pre-flight that inlines the
    wrap-detection recipe before any drafting step."""
    write = _section(commit_message_md, "## WRITE mode workflow")
    assert "### 0." in write, "WRITE mode has no Step 0 pre-flight heading"
    preflight = write.split("### 0.", 1)[1].split("### 1.", 1)[0]
    heading = preflight.splitlines()[0].lower()
    assert "pre-flight" in heading or "detect" in heading, (
        "Step 0 heading is not the wrap-detection pre-flight"
    )
    assert detection_recipe in preflight, (
        "Step 0 pre-flight does not inline the wrap-detection recipe"
    )


def test_preflight_recipe_matches_format_body_ssot(
    commit_message_md: str, detection_recipe: str
) -> None:
    """The pre-flight recipe must be byte-identical to the format-body.md source.
    A bare substring check is not enough: it would pass even if an extra pipeline
    stage were appended inside the same span (e.g. ``… | head -100 | sed …``), so
    assert every backticked recipe span in commit-message matches verbatim."""
    spans = _recipe_spans(commit_message_md)
    assert spans, (
        "commit-message no longer carries the backticked wrap-detection recipe"
    )
    for span in spans:
        assert span == detection_recipe, (
            f"commit-message carries a wrap-detection span {span!r} that is not "
            f"byte-identical to the format-body.md recipe {detection_recipe!r}"
        )


def test_write_output_requires_detected_conventions_preamble(
    commit_message_md: str,
) -> None:
    """Every WRITE proposal must open with the Detected-conventions preamble —
    the keystone fix that turns a silent omission into a falsifiable claim.
    Assert it lives as the first non-empty line of the fenced output template,
    not merely somewhere in §8: a match anywhere would stay green even if the
    real template regressed while the explanatory example kept the words."""
    write = _section(commit_message_md, "## WRITE mode workflow")
    output = write.split("### 8.", 1)[1]
    block = re.search(r"```[^\n]*\n(.*?)```", output, re.DOTALL)
    assert block, "§8 output has no fenced example block"
    first_line = next((ln for ln in block.group(1).splitlines() if ln.strip()), "")
    assert first_line.startswith("Detected:"), (
        "the §8 fenced output template must open with the Detected-conventions "
        f"preamble; its first non-empty line is {first_line!r}"
    )
    assert "body wrap" in first_line, (
        "the Detected-conventions preamble does not declare the body-wrap style"
    )


def test_write_mode_names_the_skip_detection_anti_pattern(
    commit_message_md: str,
) -> None:
    """A named anti-pattern must cover drafting a body without running the
    detection — gives recurrence a labelled handle for reviewers to point at."""
    anti = _section(commit_message_md, "## Anti-patterns")
    lowered = anti.lower()
    assert "detection" in lowered and (
        "detected-conventions" in lowered or "preamble" in lowered
    ), "Anti-patterns lacks the skip-wrap-detection entry"


@pytest.fixture(scope="session")
def hard_wrap_entry(references_dir: Path) -> str:
    """The `hard-wrapped-paragraph` entry body from the smells catalog."""
    text = (references_dir / "commit-smells.md").read_text(encoding="utf-8")
    marker = "### `hard-wrapped-paragraph`"
    assert marker in text, "commit-smells.md has no hard-wrapped-paragraph entry"
    return text.split(marker, 1)[1].split("\n### ", 1)[0].split("\n## ", 1)[0]


@pytest.fixture(scope="session")
def hard_wrap_pattern(hard_wrap_entry: str) -> str:
    """Just the entry's **Pattern** paragraph — where the exemptions are listed.

    Scoped deliberately rather than searching the whole entry: the Fix advice
    names `commit-body-reflow` and what it preserves, so a whole-entry keyword
    search for an exemption matches prose that is not the exemption list and
    stays green when the list loses a member. Found by mutation — dropping the
    trailer exemption from Pattern left a whole-entry check passing.
    """
    line = next(
        (ln for ln in hard_wrap_entry.splitlines() if ln.startswith("**Pattern**")), None
    )
    assert line, "hard-wrapped-paragraph entry has no **Pattern** paragraph"
    return line.lower()


@pytest.fixture(scope="session")
def linter():
    """The repo's commit-style linter, loaded from its path (`.github/scripts/`
    is not an importable package)."""
    spec = importlib.util.spec_from_file_location("lint_commit_message", _LINTER)
    assert spec and spec.loader, f"cannot load {_LINTER}"
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_catalog_entry_matches_what_the_gate_enforces(
    hard_wrap_entry: str, hard_wrap_pattern: str, linter
) -> None:
    """The entry's exemptions are the ones the repo's gate actually implements.

    The router's own principle is that discovery and enforcement state the same
    rules, and this repo carries all three surfaces — CONTRIBUTING declares the
    convention, `lint_commit_message.py` gates it, and this catalog is the
    discovery side. So the entry is not checked against a hardcoded list but
    against the linter itself: each documented exemption is fed to it as a body
    of that shape and must pass, which fails if the catalog claims an exemption
    the gate does not grant or the gate drops one the catalog still promises.

    `tests/repo/test_commit_message.py` already pins that the linter behaves
    this way; what is new here is that the skill's description of it is true.
    """
    subject = "fix(git-toolkit): probe the body-shape rule"
    skills = {"coding-principles", "docs-steward", "git-toolkit", "oss-repository-conventions"}
    for label, phrase, body in _EXEMPTIONS:
        assert phrase in hard_wrap_pattern, (
            f"the entry's Pattern paragraph does not name the {label} exemption"
            f" the gate implements (looked for {phrase!r})"
        )
        errors = linter.lint(f"{subject}\n\n{body}", skills)
        assert not errors, (
            f"entry documents the {label} as exempt, but the gate rejects that shape: {errors}"
        )
    # Anti-vacuity, and the carve-out in one: if the probes above passed because
    # the shape check had stopped running, these would pass too.
    assert linter.lint(f"{subject}\n\n{_WRAPPED_BODY}", skills), (
        "a plainly wrapped paragraph is accepted — the gate's shape check is not running,"
        " so the exemption probes above prove nothing"
    )
    assert linter.lint(f"{subject}\n\n{_LIGHT_INDENT_BODY}", skills), (
        "a 1-3 space indent is treated as a block, so lightly indented prose dodges the rule"
    )
    assert "1–3 space" in hard_wrap_entry or "1-3 space" in hard_wrap_entry, (
        "entry does not state that a 1-3 space indent is not a block"
    )


def test_review_grades_the_hard_wrap_rule(commit_message_md: str) -> None:
    """REVIEW mode must cite the id and grade it, in both directions.

    Citing it in the §0 catalog without a Step 2 row would leave the rule
    nameable but never evaluated — the same shape as the gap it closes.
    """
    review = _section(commit_message_md, "## REVIEW mode workflow")
    catalog = review.split("### 0.", 1)[1].split("### 1.", 1)[0]
    assert "`hard-wrapped-paragraph`" in catalog, (
        "REVIEW §0 rule catalog does not cite hard-wrapped-paragraph"
    )
    row = next(
        (ln for ln in review.splitlines() if "`hard-wrapped-paragraph`" in ln and ln.startswith("|")),
        None,
    )
    assert row, "REVIEW Step 2 table has no hard-wrapped-paragraph row"
    assert "`error`" in row, "the row does not grade the rule an error where it fires"
    assert "`N/A`" in row, (
        "the row does not state the N/A case — the rule must not fire in a hard-wrap repo"
    )


def test_review_establishes_the_convention_it_grades_against(
    commit_message_md: str, detection_recipe: str
) -> None:
    """REVIEW must run the wrap detection and state its verdict in the preamble.

    Adding the graded row is only half the fix. `body-wrap` and
    `hard-wrapped-paragraph` grade opposite directions of one convention, so
    both are undecidable until it is known — and WRITE mode's mandatory
    pre-flight belongs to WRITE mode. Without this, REVIEW would carry the
    verdict while leaving its input unstated, which is the same shape as the
    gap the rule closes: a reader seeing both rules `N/A` could not tell a
    hard-wrapping repo from a detection that never ran.
    """
    review = _section(commit_message_md, "## REVIEW mode workflow")
    step2 = review.split("### 2.", 1)[1].split("### 3.", 1)[0]
    # The recipe itself, not a mention of the file it lives in: the `body-wrap`
    # row already cites format-body.md, so a check that would accept the
    # filename passes on text that predates this rule and asserts nothing.
    # Mutation found exactly that — deleting the detection left it green.
    assert detection_recipe in step2, (
        "REVIEW Step 2 does not carry the wrap-detection recipe, so the two "
        "wrap rules are graded against a convention nothing establishes"
    )
    output = review.split("### 4.", 1)[1]
    spec = output.split("```", 1)[0]
    # The enumerated preamble item, not the word "wrap": the paragraph that
    # follows explains the requirement using "the two wrap rules", so a bare
    # keyword survives deleting the requirement it is meant to guard.
    assert "body-wrap convention" in spec, (
        "REVIEW §4 does not name the detected body-wrap convention among the "
        "parts its preamble must carry"
    )
    block = re.search(r"```[^\n]*\n(.*?)```", output, re.DOTALL)
    assert block, "REVIEW §4 output has no fenced example block"
    example = block.group(1)
    first_line = next((ln for ln in example.splitlines() if ln.strip()), "")
    assert "wrap" in first_line.lower(), (
        "the §4 example preamble does not carry the detected wrap convention; "
        f"its first line is {first_line!r}"
    )
    # The worked example is what a reader copies, so it has to show the rule it
    # now grades — otherwise the pairing silently stops being demonstrated while
    # the spec above still claims it.
    assert any(
        ln.startswith("|") and "Hard-wrapped paragraph" in ln for ln in example.splitlines()
    ), "the §4 example result table does not show the hard-wrapped-paragraph rule"


def test_review_names_the_ungraded_verdict_anti_pattern(commit_message_md: str) -> None:
    """The third leg of the tightening the WRITE half already carries.

    A pre-flight and a preamble stop the honest mistake; the named anti-pattern
    is what gives recurrence a handle a reviewer can point at, which is why the
    WRITE half has all three. Its REVIEW analogue is the both-`N/A` reading,
    because that is the one failure that looks like a pass.
    """
    anti = _section(commit_message_md, "## Anti-patterns").lower()
    entry = next(
        (ln for ln in anti.splitlines() if "`n/a`" in ln and "wrap" in ln), None
    )
    assert entry, (
        "Anti-patterns does not name the ungraded-wrap-verdict failure — grading "
        "both wrap rules N/A must be called out as an unrun detection, not a result"
    )
    assert "hard-wrapped-paragraph" in entry and "body-wrap" in entry, (
        "the anti-pattern does not name both wrap rules, so it does not identify "
        f"the both-N/A signature it exists to flag: {entry!r}"
    )


def test_amend_inherits_the_wrap_detection(commit_message_md: str) -> None:
    """AMEND reaches Step 2's checks, so it must reach Step 2's detection too.

    AMEND rewrites a body rather than only reading one, so it can introduce the
    very defect the rule catches. Its pointer names the Step 2 *table*, and the
    detection is prose above that table — close enough to read past, which is
    why the pointer says so explicitly.
    """
    amend = _section(commit_message_md, "## AMEND mode workflow")
    pointer = next(
        (ln for ln in amend.splitlines() if "Step 2 table" in ln), None
    )
    assert pointer, "AMEND no longer points at the REVIEW Step 2 checks"
    assert "wrap detection" in pointer, (
        "AMEND's pointer names the Step 2 table without its wrap detection, so a "
        "reworded body can be reflowed against a convention nothing established"
    )
