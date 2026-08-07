"""Fleet-wide syntax check on the TypeScript the skills ship.

The per-skill lane in `tests/skills/coding_principles/test_examples.py` parses
python and bash with the standard library alone. TypeScript needs a compiler, so
it waited for the node toolchain the markdown gate introduced — and it is
fleet-wide from the start because a TypeScript fence carries no `<placeholder>`
problem: the shell lanes are the ones a placeholder argument breaks, and the
convention that settles them is still open.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

from tests.support.fences import fences_under

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SKILLS = _REPO_ROOT / "skills"
_PARSER = _REPO_ROOT / "tests" / "support" / "parse_typescript.mjs"

# `parse_typescript.mjs` exits with this when the pinned compiler is absent, so
# a machine that has never run `npm ci` skips the lane instead of failing it.
_NO_TOOLCHAIN = 3

# Sent with every batch, because "the parser found nothing" and "the parser is
# no longer looking" produce the same green. The broken control proves it still
# reports; the valid one proves what it reports on. The valid control is an
# `enum` deliberately: it is the construct node's built-in type stripper rejects
# as unsupported, so swapping this lane for the cheaper tool fails here instead
# of quietly reclassifying valid samples as defects.
_CONTROLS = {
    "control://must-fail": "const broken: number = ;",
    "control://must-pass": "enum Direction { Up, Down }\nnamespace N { export const x = 1; }",
}


def _no_toolchain(reason: str) -> None:
    """Skip, unless this is the job that exists to run the lane.

    Skipping is right on a machine that has never run `npm ci` — the alternative
    is a suite that fails for a reason unrelated to what the contributor
    changed. It is wrong in CI's `typescript` job, where a skip is a green tick
    over an unchecked sample, so that job sets the variable and gets a failure.
    """
    if os.environ.get("REQUIRE_TYPESCRIPT_LANE"):
        raise AssertionError(f"the TypeScript lane is required here but could not run: {reason}")
    pytest.skip(reason)


def _typescript_samples() -> list[tuple[str, int, str]]:
    """(relative path, 1-based fence line, body) for every TypeScript fence."""
    return [
        (rel, line, body)
        for rel, line, lang, body in fences_under(_SKILLS, relative_to=_REPO_ROOT)
        if lang == "typescript"
    ]


def test_typescript_samples_parse() -> None:
    """Every `typescript` fence in the fleet is syntactically valid.

    Syntax only. The samples name types and helpers that exist nowhere, which is
    the right shape for an illustration and the reason a typecheck would report
    noise instead of defects — so `enum`, `namespace`, and parameter properties
    pass here, where node's own type stripper rejects all three as unsupported.
    That distinction is the whole argument for spending a compiler on this: a
    guard that fails on valid content gets suppressed, and a suppressed guard is
    worse than an absent one.
    """
    node = shutil.which("node")
    if not node:
        _no_toolchain("node is not installed")
        return

    samples = _typescript_samples()
    payload = [{"id": f"{rel}:{line}", "source": body} for rel, line, body in samples]
    payload += [{"id": name, "source": source} for name, source in _CONTROLS.items()]

    done = subprocess.run(
        [node, str(_PARSER)],
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        check=False,
        cwd=_REPO_ROOT,
    )
    if done.returncode == _NO_TOOLCHAIN:
        _no_toolchain(done.stderr.strip() or "the pinned typescript is not installed")
        return
    assert done.returncode == 0, f"the TypeScript parser failed to run: {done.stderr.strip()}"

    result = json.loads(done.stdout)
    flagged = {problem["id"] for problem in result["problems"]}

    # The controls are checked before the samples are trusted: a parser that has
    # stopped reporting reports the samples clean too, and that is the shape
    # every lane in this file is guarding against somewhere else.
    assert "control://must-fail" in flagged, (
        "the broken control parsed cleanly, so this run proves nothing about the"
        " samples either — the parser is no longer reporting"
    )
    assert "control://must-pass" not in flagged, (
        "the valid control was flagged; a parser rejecting `enum` or `namespace`"
        " is a type stripper rather than a compiler, and would report valid"
        " samples as defects"
    )

    problems = [
        f"{p['id']} (sample line {p['line']}): {p['message']}"
        for p in result["problems"]
        if p["id"] not in _CONTROLS
    ]
    assert not problems, "malformed TypeScript samples:\n" + "\n".join(problems)

    # Anti-vacuity, the same guard the python and bash lanes carry. A silent zero
    # means the fence pattern stopped matching or the alias map lost a spelling,
    # and the lane went dark while still reporting green — the failure a parser
    # guard is least able to notice about itself. Counted over the samples, not
    # the payload, or the controls alone would satisfy it.
    assert samples, "no TypeScript fence was checked — the fence pattern has gone stale"
    assert result["checked"] == len(payload), (
        f"sent {len(payload)} samples, parser reports {result['checked']} checked"
    )


def test_the_lane_reaches_every_skill_that_ships_typescript() -> None:
    """The fleet-wide claim is asserted, not assumed.

    Scoping this lane to one skill would be the easy mistake — coding-principles
    holds all but one of the fences, and the one that lives elsewhere is tagged
    `ts` rather than `typescript`, so it is invisible to any lane that reads the
    info string literally. That single fence is the whole reason the alias map
    exists, and this is what stops it being dropped as an edge case.
    """
    skills_with_samples = {rel.split("/")[1] for rel, _, _ in _typescript_samples()}

    assert len(skills_with_samples) > 1, (
        "every TypeScript sample now resolves to one skill; if that is real the"
        " lane is per-skill, and if it is not, the alias map has lost a spelling"
        f" (found: {sorted(skills_with_samples)})"
    )
