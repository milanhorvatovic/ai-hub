"""Output-contract tests for the release-notes capability.

The grouping mode (conventional-commits vs. labels vs. flat) and the CHANGELOG
style are detected per-repo and drive the whole document, but neither was forced
to run nor exposed in the output — the same "rule stated, compliance implicit,
no output evidence" hole that #7 closed in commit-message WRITE mode. Under habit
pressure an agent could group by conventional-commits types in a repo that
doesn't use them, or ignore an existing Keep-a-Changelog format, and the omission
was invisible. These tests pin the three composing tightenings: a mandatory Step 0
pre-flight that detects both, a Detected-conventions line in the Step 6 preamble,
and a named anti-pattern for skipping the detection.

The section/step helpers are fence-aware on purpose: the capability's Step 4
example fences a `## [vX.Y.Z]` markdown sample, so a naive "split on a heading
line" would mistake that for a real section boundary and truncate the workflow.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest


@pytest.fixture(scope="session")
def release_notes_md(capabilities_dir: Path) -> str:
    path = capabilities_dir / "release-notes" / "capability.md"
    assert path.is_file(), "release-notes/capability.md not found"
    return path.read_text(encoding="utf-8")


def _lines_with_fence_state(text: str) -> list[tuple[str, bool]]:
    """Each line paired with whether it sits *inside* a ``` code fence. The fence
    delimiter lines themselves are reported as outside, so headings that open or
    close a block are never mistaken for section boundaries."""
    out: list[tuple[str, bool]] = []
    in_fence = False
    for ln in text.splitlines():
        if ln.lstrip().startswith("```"):
            out.append((ln, False))
            in_fence = not in_fence
        else:
            out.append((ln, in_fence))
    return out


def _block(text: str, marker: str, *stops: str) -> str:
    """Body of the section/step opened by a line starting with `marker`, up to the
    next real (non-fenced) heading line starting with any of `stops`."""
    lines = _lines_with_fence_state(text)
    start = next(
        (i for i, (ln, fenced) in enumerate(lines) if not fenced and ln.startswith(marker)),
        None,
    )
    assert start is not None, f"section {marker!r} not found"
    body: list[str] = []
    for ln, fenced in lines[start + 1 :]:
        if not fenced and any(ln.startswith(s) for s in stops):
            break
        body.append(ln)
    return "\n".join(body)


def _heading_index(text: str, marker: str) -> int:
    """Line index of the first *non-fenced* line starting with `marker`, or -1.

    Fence-aware for the same reason `_block` is: a heading-shaped line inside a
    fenced example must not be mistaken for a real workflow step."""
    for i, (ln, fenced) in enumerate(_lines_with_fence_state(text)):
        if not fenced and ln.startswith(marker):
            return i
    return -1


def _fenced_block_with(text: str, needle: str) -> list[str] | None:
    """Lines of the first ``` fenced block that contains a line holding `needle`.

    Selecting by content, not position, keeps the Step 6 assertions pinned to the
    output template even if an earlier fenced example (e.g. a command snippet) is
    added ahead of it in the same section."""
    for m in re.finditer(r"```[^\n]*\n(.*?)```", text, re.DOTALL):
        block_lines = m.group(1).splitlines()
        if any(needle in ln for ln in block_lines):
            return block_lines
    return None


def test_workflow_has_preflight_detection_step(release_notes_md: str) -> None:
    """The Workflow must open with a Step 0 pre-flight that detects both the
    grouping mode and the CHANGELOG style before any gather/classify step —
    making the detection mandatory rather than a branch buried in Step 2."""
    preflight = _block(release_notes_md, "### 0.", "### ", "## ")
    heading_line = next(
        (
            ln
            for ln, fenced in _lines_with_fence_state(release_notes_md)
            if not fenced and ln.startswith("### 0.")
        ),
        "",
    ).lower()
    assert "pre-flight" in heading_line or "detect" in heading_line, (
        "Step 0 heading is not the detection pre-flight"
    )
    lowered = preflight.lower()
    assert "grouping" in lowered, "Step 0 pre-flight does not detect the grouping mode"
    assert "changelog" in lowered, "Step 0 pre-flight does not detect the CHANGELOG style"

    # "must open with … before any gather/classify step" is an ordering claim —
    # assert it, so moving detection after Step 1 fails rather than passing on
    # the mere existence of a Step 0 heading.
    step0_idx = _heading_index(release_notes_md, "### 0.")
    step1_idx = _heading_index(release_notes_md, "### 1.")
    assert step1_idx != -1, "Workflow has no Step 1 to order the pre-flight against"
    assert 0 <= step0_idx < step1_idx, (
        "Step 0 pre-flight must precede Step 1 (gather/classify) so detection "
        f"runs first; got Step 0 at line {step0_idx}, Step 1 at line {step1_idx}"
    )


def test_preflight_inlines_a_grouping_detection_recipe(release_notes_md: str) -> None:
    """The pre-flight must inline a concrete `git log … | head …` sampling recipe
    so the grouping call is a measured fact, not an assertion taken on faith
    (mirrors commit-message Step 0's inlined wrap recipe)."""
    preflight = _block(release_notes_md, "### 0.", "### ", "## ")
    assert "git log" in preflight and "| head" in preflight, (
        "Step 0 pre-flight does not inline a 'git log … | head …' sampling recipe"
    )


def test_step6_preamble_declares_detected_conventions(release_notes_md: str) -> None:
    """The Step 6 output preamble must carry a Detected line declaring the
    grouping mode and CHANGELOG style, positioned before the Range line — the
    keystone that turns a silent decision into a falsifiable claim."""
    step6 = _block(release_notes_md, "### 6.", "### ", "## ")
    lines = _fenced_block_with(step6, "Range:")
    assert lines is not None, "Step 6 has no fenced output template with a Range: line"
    detected = next((ln for ln in lines if ln.strip().startswith("Detected:")), None)
    assert detected is not None, (
        "the Step 6 output template carries no 'Detected:' preamble line"
    )
    assert "grouping" in detected, "Detected line does not declare the grouping mode"
    assert "changelog style" in detected.lower(), (
        "Detected line does not declare the CHANGELOG style"
    )
    detected_idx = lines.index(detected)
    range_idx = next(
        (i for i, ln in enumerate(lines) if ln.strip().startswith("Range:")), None
    )
    assert range_idx is not None, "Step 6 template lost its Range line"
    assert detected_idx < range_idx, (
        "the Detected line must precede the Range line in the preamble"
    )


def test_step6_preamble_renders_the_detected_forge(release_notes_md: str) -> None:
    """The Inputs forge guard promises to surface the detected forge in the
    proposal preamble; the Step 6 output template must actually render a
    `forge=` line so that claim isn't documentation-only."""
    step6 = _block(release_notes_md, "### 6.", "### ", "## ")
    lines = _fenced_block_with(step6, "Range:")
    assert lines is not None, "Step 6 has no fenced output template with a Range: line"
    assert any(ln.strip().startswith("forge=") for ln in lines), (
        "the Step 6 output template renders no 'forge=' line, so the Inputs "
        "forge guard's promise to surface it stays documentation-only"
    )


def test_names_the_skip_detection_anti_pattern(release_notes_md: str) -> None:
    """A named anti-pattern must cover emitting grouped notes without running the
    detection and stating it — gives the recurrence a labelled handle."""
    anti = _block(release_notes_md, "## Anti-patterns", "## ")
    lowered = anti.lower()
    assert "grouping" in lowered and "changelog" in lowered, (
        "Anti-patterns lacks the skip-detection entry naming grouping + CHANGELOG"
    )
    assert "detection" in lowered or "detected" in lowered, (
        "the skip-detection anti-pattern does not reference the detection step"
    )
    assert "preamble" in lowered or "step 6" in lowered, (
        "the skip-detection anti-pattern does not tie back to the output preamble"
    )
