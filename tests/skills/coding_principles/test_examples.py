"""Fidelity checks on the code this skill shows its reader.

The skill teaches by example, so a malformed example is a defect in the
teaching, not a cosmetic one. Parsing the samples is a fleet-wide concern and
lives in `tests/skills/test_code_samples.py`; what stays here is the contract no
other skill has — that the worked review's line citations point at the lines
they claim to.
"""

from __future__ import annotations

import re
from pathlib import Path

from tests.support.fences import fences_in

# `[path:line]` at the head of a finding, and the first backticked token in the
# rest of that line — the thing the finding says is at that location.
_CITATION = re.compile(r"^- \[(?P<path>[^\]:]+):(?P<line>\d+)\](?P<rest>.*)$", re.M)
_FIRST_TOKEN = re.compile(r"`([^`]+)`")


def test_worked_review_cites_the_lines_it_names(capabilities_dir: Path) -> None:
    """The worked review's `[file:line]` findings resolve to the lines they describe.

    The sample argues that inventing a line number points a reader at code that
    is not the problem, so its own citations have to survive the check it asks
    for. Each finding names its subject in backticks first; that token must
    appear on the cited line of the diff the file shows. Findings with no line
    number (one is deliberately anchored to the file, being about something the
    diff omits) carry nothing to verify and are skipped.
    """
    examples = capabilities_dir / "review" / "references" / "examples.md"
    text = examples.read_text(encoding="utf-8")

    diff = next((f.body for f in fences_in(examples) if f.language == "diff"), None)
    assert diff, "worked review no longer carries a diff block to check against"

    new_file = re.search(r"^\+\+\+ b/(\S+)", diff, re.M)
    assert new_file, "diff block has no +++ header, so citations have no path to resolve against"
    diff_path = new_file.group(1)

    # The mapping below numbers `+` lines consecutively from the hunk's new-file
    # start, which is only the real new-file numbering when the hunk is the whole
    # diff and carries no context lines. That is the shape this worked example is
    # authored in, so the invariant is asserted rather than assumed — a full
    # unified-diff walk would be machinery for one hand-written file, but silently
    # mis-mapping when someone adds a context line would be worse than either.
    headers = re.findall(r"^@@ -\d+,(\d+) \+(\d+),(\d+) @@", diff, re.M)
    assert len(headers) == 1, (
        f"worked diff carries {len(headers)} hunks; the citation mapping below numbers"
        " one all-added hunk, so more than one needs a real unified-diff walk first"
    )
    removed, start, added = (int(group) for group in headers[0])

    body_lines = [ln for ln in diff.splitlines() if not ln.startswith(("@@", "---", "+++"))]
    minus = [ln for ln in body_lines if ln.startswith("-")]
    plus = [ln[1:] for ln in body_lines if ln.startswith("+")]
    # No `.strip()` here: a blank context line in a unified diff is a lone space,
    # and stripping it would erase the only evidence that it is context — the
    # line would then slip past this assertion and shift every citation after it.
    context = [ln for ln in body_lines if not ln.startswith(("-", "+"))]
    assert not context, (
        f"worked diff carries {len(context)} context line(s); new-file numbering counts"
        " those too, which the citation mapping below does not — keep the hunk all-added"
        " or teach the mapping to walk context"
    )
    assert (len(minus), len(plus)) == (removed, added), (
        f"hunk header claims {removed} removed / {added} added,"
        f" block shows {len(minus)} / {len(plus)}"
    )

    numbered = {start + i: content for i, content in enumerate(plus)}

    problems: list[str] = []
    cited = 0
    for m in _CITATION.finditer(text):
        cited += 1
        if m.group("path") != diff_path:
            problems.append(
                f"finding cites {m.group('path')!r}, but the diff shown is {diff_path!r}"
            )
            continue
        lineno = int(m.group("line"))
        target = numbered.get(lineno)
        if target is None:
            problems.append(f"finding cites line {lineno}, outside the diff's {start}..{max(numbered)}")
            continue
        token = _FIRST_TOKEN.search(m.group("rest"))
        assert token, f"finding at line {lineno} names no backticked subject to verify"
        if token.group(1) not in target:
            problems.append(
                f"finding cites line {lineno} for {token.group(1)!r},"
                f" but that line reads {target.strip()!r}"
            )
    assert problems == [], "worked review anchors drifted:\n" + "\n".join(problems)
    # Anti-vacuity, as in the sample lanes above: with no numbered finding to
    # resolve, this whole check passes without verifying anything, and the file
    # it guards is one whose findings were mis-anchored the first time it shipped.
    assert cited, "worked review carries no `[file:line]` finding — nothing was verified"
