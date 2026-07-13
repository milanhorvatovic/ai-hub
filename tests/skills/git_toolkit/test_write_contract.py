"""WRITE-mode output-contract tests for the commit-message capability.

The body-wrap detection was documented as a rule, but nothing forced it to run
and nothing in the output exposed whether it had — so an agent under habit
pressure could hard-wrap a body in a repo with no hard-wrap convention. These
tests pin the three composing tightenings that close that hole: a mandatory
Step 0 pre-flight that runs the wrap-detection recipe, a Detected-conventions
preamble on every WRITE proposal, and a named anti-pattern for skipping the
check. The recipe is read from its single source of truth (format-body.md) and
asserted inlined byte-identically into the pre-flight.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

# A backtick-delimited inline code span.
_BACKTICK_SPAN = re.compile(r"`([^`]+)`")


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
