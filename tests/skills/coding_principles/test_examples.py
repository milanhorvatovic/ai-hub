"""Fidelity checks on the code this skill shows its reader.

The skill teaches by example, so a malformed example is a defect in the
teaching, not a cosmetic one — and neither the fleet structure suite nor the
pointer contract looks inside a fence. Two things are checkable without a
toolchain: that the python and bash samples parse, and that the worked review's
line citations point at the lines they claim to.
"""

from __future__ import annotations

import ast
import re
import shutil
import subprocess
from pathlib import Path

from tests.support.fences import fences_in as _fences_in
from tests.support.fences import fences_under

# `[path:line]` at the head of a finding, and the first backticked token in the
# rest of that line — the thing the finding says is at that location.
_CITATION = re.compile(r"^- \[(?P<path>[^\]:]+):(?P<line>\d+)\](?P<rest>.*)$", re.M)
_FIRST_TOKEN = re.compile(r"`([^`]+)`")


def _usable_bash() -> str | None:
    """Path to a bash that can actually parse a script, or None.

    `shutil.which` answers "is there something named bash on PATH", which is not
    the same question: Windows runners resolve `bash` to the WSL launcher stub,
    which exists, runs, and exits non-zero without parsing anything — reporting
    every sample as malformed with an empty stderr. Probing a known-good script
    is the only honest way to tell an interpreter from a name.
    """
    exe = shutil.which("bash")
    if not exe:
        return None
    probe = subprocess.run(
        [exe, "-n"], input="true\n", text=True, capture_output=True, check=False
    )
    return exe if probe.returncode == 0 else None


def _fences(skill_root: Path) -> list[tuple[str, int, str, str]]:
    """(relative path, 1-based fence line, language, dedented body) for every
    fenced block in the skill tree."""
    return fences_under(skill_root)


def test_python_and_bash_samples_parse(skill_root: Path) -> None:
    """Every `python` and `bash` fence is syntactically valid.

    Parsing, not resolution: the samples are fragments that name types and
    helpers defined nowhere (`DEFAULT_SETTINGS`, `OrderSchema`), which is the
    right shape for an illustration and means a typecheck would be noise. The
    `rust` and `typescript` fences go unchecked because neither toolchain is a
    test dependency.

    Deliberately scoped to this skill rather than the fleet: sibling skills
    document CLI invocations with `<placeholder>` arguments, where the angle
    brackets read as redirections and fail `bash -n` by design, not by defect.

    The bash lane needs an interpreter that works, not merely one on PATH, so it
    goes quiet where there is none — the python lane still runs everywhere, and
    the platforms carrying the required checks have a real bash.
    """
    bash = _usable_bash()
    problems: list[str] = []
    checked_python = checked_bash = 0
    for rel, line, lang, body in _fences(skill_root):
        if lang == "python":
            checked_python += 1
            try:
                ast.parse(body)
            except SyntaxError as exc:
                problems.append(f"{rel}:{line} python: {exc.msg} (sample line {exc.lineno})")
        elif lang == "bash" and bash:
            checked_bash += 1
            done = subprocess.run(
                [bash, "-n"], input=body, text=True, capture_output=True, check=False
            )
            if done.returncode:
                detail = done.stderr.strip().splitlines()[-1] if done.stderr.strip() else "?"
                problems.append(f"{rel}:{line} bash: {detail}")
    assert not problems, "malformed code samples:\n" + "\n".join(problems)
    # Anti-vacuity, per lane. A silent zero means the fence pattern stopped
    # matching and the lane went dark while still reporting green — the failure
    # a parser guard is least able to notice about itself. Python is
    # unconditional; bash is asserted only where an interpreter exists to run.
    assert checked_python, "no python fence was checked — the fence pattern has gone stale"
    assert not bash or checked_bash, "bash is usable but no bash fence was checked"


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

    diff = next((body for _, lang, body in _fences_in(examples) if lang == "diff"), None)
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
