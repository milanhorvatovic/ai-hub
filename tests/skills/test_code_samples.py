"""Syntax checks on every code sample in the repo's markdown.

A malformed example is a defect in the teaching, not a cosmetic one, and nothing
else in the suite looks inside a fence — the structure checks read frontmatter
and pointers, the per-skill contracts read headings and anchors. Three languages
are checkable here: python and bash need only what the runner already has, and
TypeScript needs the compiler the markdown gate's node toolchain now pins.

The scan is the whole working tree rather than `skills/`, because the argument
for parsing a sample does not stop at the distribution boundary: a broken
command in CONTRIBUTING is one a contributor runs. That costs nothing today —
the repo's own docs were already clean when the scope widened — and it means a
setup step cannot rot into something that no longer parses.

Rust is deliberately absent. A fence check belongs in a language's minimum set
when the language parses with a toolchain CI installs for another reason, and
rust would mean rustup for eighteen fences plus a wrapping heuristic — the
samples are fragments, and guessing the wrapper turns valid content into a red
build. The split is a stated rule rather than an accident of which languages
happen to be cheap.
"""

from __future__ import annotations

import ast
import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import NoReturn

import pytest

from tests.support.fences import Fence, GitUnavailable, fences_under

_REPO_ROOT = Path(__file__).resolve().parents[2]
_PARSER = _REPO_ROOT / "tests" / "support" / "parse_typescript.mjs"

# Every pipe carrying a sample is UTF-8 by instruction, never by locale. With a
# bare `text=True`, Python encodes subprocess stdin with the platform default —
# cp1252 on a Windows runner — and a sample containing an arrow or an accent
# raises UnicodeEncodeError before the parser ever sees it. That is the checker
# failing on content that is perfectly valid, which is the one outcome these
# lanes must never produce. Found on a Windows runner, by a `→` in a shell
# sample that this change brought into scope for the first time.
_TEXT_UTF8 = {"text": True, "encoding": "utf-8"}

# Probes bash with a non-ASCII byte deliberately, so an encoding regression
# surfaces here — as "the interpreter cannot take our input" — instead of as a
# malformed-sample report against the first sample that happens to contain one.
_PROBE = "# \N{RIGHTWARDS ARROW} utf-8 round-trip\ntrue\n"

# `parse_typescript.mjs` exits with this when the pinned compiler is absent, so
# a machine that has never run `npm ci` skips the lane instead of failing it.
_NO_TOOLCHAIN = 3

# The info strings a lane parses, in the spellings the content actually writes.
_CHECKED_SPELLINGS = frozenset({"bash", "sh", "python", "typescript", "ts"})

# The rest, and why each has no lane. Data formats are validated where they are
# consumed rather than where they are illustrated; `rust` is the one language
# deliberately without a lane, per the rule in this module's docstring.
_UNCHECKED_SPELLINGS = frozenset(
    {
        "rust",  # a toolchain CI installs for nothing else, plus a wrapping guess
        "yaml",  # workflow and config illustrations; the real files are linted in place
        "json",
        "jsonl",
        "toml",
        "ini",
        "dotenv",
        "gitattributes",
        "diff",  # a worked review's subject, checked by the anchor test instead
        "markdown",  # prose samples; Prettier owns the tracked files
        "text",  # output transcripts and trees, not a language
    }
)

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


def _no_toolchain(reason: str) -> NoReturn:
    """Skip, unless this is the job that exists to run the lanes.

    Skipping is right on a machine that has never run `npm ci` — the alternative
    is a suite that fails for a reason unrelated to what the contributor
    changed. It is wrong in the CI job built to run these lanes, where a skip is
    a green tick over an unchecked sample, so that job sets the variable and
    gets a failure instead.

    Every lane routes its "cannot run" path through here rather than calling
    `pytest.skip` directly. The TypeScript lane had this protection first and the
    others did not, which left the guarantee resting on the accident that CI
    runners happen to ship bash: true today, and not a thing the suite checked.
    """
    if os.environ.get("REQUIRE_SAMPLE_LANES"):
        raise AssertionError(f"a sample lane is required here but could not run: {reason}")
    pytest.skip(reason)


def _tracked_fences() -> list[Fence]:
    """Every fence in the tracked tree, or a skip if the file list is unobtainable."""
    try:
        return fences_under(_REPO_ROOT)
    except GitUnavailable as exc:
        _no_toolchain(str(exc))


def _samples(language: str) -> list[Fence]:
    """Every runnable fence of one language in the tracked tree.

    Template fences are excluded here rather than at each call site, so a lane
    cannot forget the exemption and report a shape-to-fill-in as malformed.
    """
    return [
        fence
        for fence in _tracked_fences()
        if fence.language == language and not fence.is_template
    ]


def _usable_bash() -> str | None:
    """Path to a bash that can actually parse a script, or None.

    `shutil.which` answers "is there something named bash on PATH", which is not
    the same question: Windows runners resolve `bash` to the WSL launcher stub,
    which exists, runs, and exits non-zero without parsing anything — reporting
    every sample as malformed with an empty stderr. Probing a known-good script
    is the only honest way to tell an interpreter from a name.

    The probe carries a non-ASCII character on purpose, so the pipe's encoding is
    part of what "usable" means. Get that wrong and the failure lands on the
    first sample containing an arrow, reported as a malformed sample — a true
    statement about the pipe dressed up as a false one about the content.
    """
    exe = shutil.which("bash")
    if not exe:
        return None
    probe = subprocess.run(
        [exe, "-n"], input=_PROBE, **_TEXT_UTF8, capture_output=True, check=False
    )
    return exe if probe.returncode == 0 else None


def test_python_samples_parse() -> None:
    """Every `python` fence in the tracked tree is syntactically valid.

    Parsing, not resolution: the samples are fragments naming types and helpers
    defined nowhere (`DEFAULT_SETTINGS`, `OrderSchema`), which is the right shape
    for an illustration and means a typecheck would be noise.
    """
    problems = []
    samples = _samples("python")
    for fence in samples:
        try:
            ast.parse(fence.body)
        except SyntaxError as exc:
            problems.append(f"{fence.path}:{fence.line}: {exc.msg} (sample line {exc.lineno})")

    assert not problems, "malformed python samples:\n" + "\n".join(problems)
    assert samples, "no python fence was checked — the fence pattern has gone stale"


def test_bash_samples_parse() -> None:
    """Every `bash` and `sh` fence in the tracked tree is syntactically valid.

    `sh` fences are parsed by bash, which accepts everything `sh` does and more:
    the check is weaker on those, never wrong about them. Fences marked
    `template` carry `<placeholder>` tokens a shell reads as redirections and are
    shapes to fill in rather than commands to run, so they are excluded by the
    marker at the fence rather than by a heuristic over the body.
    """
    bash = _usable_bash()
    if not bash:
        _no_toolchain("no usable bash on PATH")

    problems = []
    samples = _samples("bash")
    for fence in samples:
        done = subprocess.run(
            [bash, "-n"], input=fence.body, **_TEXT_UTF8, capture_output=True, check=False
        )
        if done.returncode:
            detail = done.stderr.strip().splitlines()[-1] if done.stderr.strip() else "?"
            problems.append(f"{fence.path}:{fence.line}: {detail}")

    assert not problems, "malformed shell samples:\n" + "\n".join(problems)
    assert samples, "no shell fence was checked — the fence pattern has gone stale"


def test_template_fences_are_exempt_because_they_are_templates() -> None:
    """The marker earns its exemption on every fence that claims it.

    A `template` marker is a contributor asserting "this is a shape, not a
    command", and nothing stops it being pasted onto a fence to silence a real
    defect. Each marked fence must therefore actually fail its parser: if one
    starts passing, it is a runnable sample wearing an exemption it no longer
    needs, and the marker should come off rather than accumulate.

    Verified for the two languages whose parser is cheap to call here. A marked
    `typescript` fence is rejected outright rather than trusted, because
    verifying it means the node round-trip and an unverified exemption is the
    thing this test exists to refuse — extend the check before marking one.

    That refusal runs before the bash probe on purpose. It needs no interpreter,
    and gating it behind one would let a machine without bash accept exactly the
    unverified exemption this test exists to reject — a check going dark for a
    reason unrelated to what it checks.
    """
    marked = [fence for fence in _tracked_fences() if fence.is_template]
    unverifiable = [
        f"{fence.path}:{fence.line} ({fence.language})"
        for fence in marked
        if fence.language not in {"bash", "python"}
    ]
    assert not unverifiable, (
        "these fences claim `template` in a language nothing here can verify the"
        " claim for, so the exemption would be taken on trust — teach this test"
        " that language's parser first:\n" + "\n".join(unverifiable)
    )

    bash = _usable_bash()
    if not bash:
        _no_toolchain("no usable bash on PATH")

    def still_fails(fence: Fence) -> bool:
        if fence.language == "python":
            try:
                ast.parse(fence.body)
            except SyntaxError:
                return True
            return False
        return (
            subprocess.run(
                [bash, "-n"], input=fence.body, **_TEXT_UTF8, capture_output=True, check=False
            ).returncode
            != 0
        )

    needless = [f"{fence.path}:{fence.line}" for fence in marked if not still_fails(fence)]

    assert not needless, (
        "these fences are marked `template` but parse fine, so the marker is"
        " hiding nothing and should come off:\n" + "\n".join(needless)
    )
    assert marked, "no fence carries the `template` marker — has the convention moved?"


def _typescript_samples() -> list[Fence]:
    """Every runnable TypeScript fence in the tracked tree."""
    return _samples("typescript")


def test_typescript_samples_parse() -> None:
    """Every `typescript` fence in the tracked tree is syntactically valid.

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

    samples = _typescript_samples()
    payload = [{"id": f"{f.path}:{f.line}", "source": f.body} for f in samples]
    payload += [{"id": name, "source": source} for name, source in _CONTROLS.items()]

    done = subprocess.run(
        [node, str(_PARSER)],
        input=json.dumps(payload),
        **_TEXT_UTF8,
        capture_output=True,
        check=False,
        cwd=_REPO_ROOT,
    )
    if done.returncode == _NO_TOOLCHAIN:
        _no_toolchain(done.stderr.strip() or "the pinned typescript is not installed")
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
    skills_with_samples = {
        fence.path.split("/")[1]
        for fence in _typescript_samples()
        if fence.path.startswith("skills/")
    }

    assert len(skills_with_samples) > 1, (
        "every TypeScript sample now resolves to one skill; if that is real the"
        " lane is per-skill, and if it is not, the alias map has lost a spelling"
        f" (found: {sorted(skills_with_samples)})"
    )


def test_every_fence_spelling_is_accounted_for() -> None:
    """A new info string is a decision, and this is where it gets made.

    The lanes are keyed to spellings, so the way coverage shrinks is that content
    starts writing `shell` or `py` and no lane is listening — every count stays
    healthy and the new samples are simply never parsed. Guessing at aliases
    ahead of time does not fix that: an alias for a spelling nobody writes cannot
    be tested. So the tree's spellings are declared instead, and an undeclared
    one fails here until someone maps it to a lane or records why it has none.
    """
    present = {fence.raw_language for fence in _tracked_fences()}
    undeclared = present - _CHECKED_SPELLINGS - _UNCHECKED_SPELLINGS

    assert not undeclared, (
        f"fences use {sorted(undeclared)}, which no lane claims and nothing"
        " declares unchecked. Map the spelling in LANGUAGE_ALIASES if a lane"
        " should parse it, or add it to _UNCHECKED_SPELLINGS with the reason"
    )
    # The declared sets describe this tree, so a spelling that leaves the content
    # should leave the list too — otherwise the lists drift into aspiration.
    assert not (_CHECKED_SPELLINGS - present), (
        f"{sorted(_CHECKED_SPELLINGS - present)} is declared checked but appears"
        " in no fence; drop it rather than carry a claim about nothing"
    )


@pytest.mark.parametrize(("spelling", "language"), [("sh", "bash"), ("ts", "typescript")])
def test_both_spellings_of_a_language_reach_its_lane(spelling: str, language: str) -> None:
    """A lane keyed to one spelling shrinks in silence, which is the defect the
    whole file is built against.

    The fleet writes two languages two ways, and dropping either alias leaves
    every other assertion here green: the lanes still find plenty of fences, the
    anti-vacuity counts still pass, and the fences spelled the other way are
    simply never parsed. Nothing else notices, so this does.
    """
    reached = [fence for fence in _samples(language) if fence.raw_language == spelling]

    assert reached, (
        f"no ```{spelling} fence reaches the {language} lane. Either the alias"
        f" map lost `{spelling}` and those samples are now unchecked, or the"
        f" content stopped using the spelling — in which case drop this case"
        " rather than the alias"
    )
