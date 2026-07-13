"""WRITE-mode output-contract tests for the commit-message capability.

Issue #7: the body-wrap detection was documented as a rule, but nothing forced
it to run and nothing in the output exposed whether it had — so an agent under
habit pressure could hard-wrap a body in a repo with no hard-wrap convention.
These tests pin the three composing tightenings that close that hole: a
mandatory Step 0 pre-flight that runs the wrap-detection recipe, a
Detected-conventions preamble on every WRITE proposal, and a named anti-pattern
for skipping the check. The inlined recipe is asserted byte-identical to the one
in format-body.md, so the rule keeps a single source of truth.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

# The wrap-detection recipe, single-sourced in references/format-body.md and
# inlined into the WRITE-mode pre-flight. Both must carry it verbatim.
_DETECTION_RECIPE = "git log --pretty=format:'%b' -20 | head -100"

# The recipe's distinctive tail ("head -100"), derived from the recipe so there
# is no second literal to keep in sync — used to locate the recipe's code span.
_RECIPE_ANCHOR = _DETECTION_RECIPE.rsplit("|", 1)[-1].strip()

# A backtick-delimited inline code span.
_BACKTICK_SPAN = re.compile(r"`([^`]+)`")


@pytest.fixture(scope="session")
def commit_message_md(capabilities_dir: Path) -> str:
    path = capabilities_dir / "commit-message" / "capability.md"
    assert path.is_file(), "commit-message/capability.md not found"
    return path.read_text(encoding="utf-8")


def _section(text: str, heading: str) -> str:
    """Return the body of a `## <heading>` section, up to the next `## `."""
    assert heading in text, f"section {heading!r} not found"
    return text.split(heading, 1)[1].split("\n## ", 1)[0]


def test_write_mode_has_preflight_detection_step(commit_message_md: str) -> None:
    """WRITE mode must open with a Step 0 pre-flight that runs the wrap-detection
    recipe before any drafting step — issue #7's 'make compliance cheap' fix."""
    write = _section(commit_message_md, "## WRITE mode workflow")
    assert "### 0." in write, "WRITE mode has no Step 0 pre-flight heading"
    preflight = write.split("### 0.", 1)[1].split("### 1.", 1)[0]
    heading = preflight.splitlines()[0].lower()
    assert "pre-flight" in heading or "detect" in heading, (
        "Step 0 heading is not the wrap-detection pre-flight"
    )
    assert _DETECTION_RECIPE in preflight, (
        "Step 0 pre-flight does not inline the wrap-detection recipe"
    )


def test_preflight_recipe_matches_format_body_ssot(
    commit_message_md: str, references_dir: Path
) -> None:
    """The inlined recipe must be byte-identical to the one in format-body.md so
    the rule keeps a single source of truth (issue #7 SSOT constraint). A bare
    substring check is not enough: it would pass even if an extra pipeline stage
    were appended inside the same code span (e.g. ``... | head -100 | sed ...``),
    so assert the whole backticked span carrying the recipe matches verbatim."""
    format_body = (references_dir / "format-body.md").read_text(encoding="utf-8")
    for label, text in (
        ("format-body.md", format_body),
        ("commit-message pre-flight", commit_message_md),
    ):
        spans = [s for s in _BACKTICK_SPAN.findall(text) if _RECIPE_ANCHOR in s]
        assert spans, (
            f"{label} no longer carries the backticked wrap-detection recipe"
        )
        for span in spans:
            assert span == _DETECTION_RECIPE, (
                f"{label} carries a wrap-detection span {span!r} that is not "
                f"byte-identical to the SSOT recipe {_DETECTION_RECIPE!r}"
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
