"""Structural contracts for the code-sample syntax gate.

The lanes that parse the shipped samples are ordinary pytest tests, and an
ordinary pytest test skips when its parser is missing. That is correct locally
and indistinguishable from success in CI, so what has to be asserted is not the
parsing — the lanes check their own work with control samples — but the wiring
that guarantees they run somewhere the parsers are present.
"""

import json
import re
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
_LINT_WORKFLOW = _REPO_ROOT / ".github" / "workflows" / "lint.yml"
_PACKAGE_JSON = _REPO_ROOT / "package.json"
_PACKAGE_LOCK = _REPO_ROOT / "package-lock.json"
_LANE = "tests/skills/test_code_samples.py"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _code_samples_job() -> str:
    """The `code-samples:` job block, up to the next job at the same indent."""
    match = re.search(
        r"^  code-samples:\n(?P<body>(?:^(?:    .*)?\n)*)", _read(_LINT_WORKFLOW), re.MULTILINE
    )
    assert match, "lint.yml has no `code-samples:` job; the lanes run nowhere with a parser"
    return match.group("body")


def test_typescript_is_pinned_to_an_exact_version() -> None:
    """A range lets CI and a contributor resolve different compilers."""
    declared = json.loads(_read(_PACKAGE_JSON))["devDependencies"]["typescript"]

    assert re.fullmatch(r"\d+\.\d+\.\d+", declared), (
        f"typescript is declared as {declared!r}; an exact version is what makes"
        " a contributor's run and CI agree"
    )
    locked = json.loads(_read(_PACKAGE_LOCK))["packages"]["node_modules/typescript"]["version"]
    assert locked == declared, f"lockfile has typescript {locked}, package.json wants {declared}"


def test_the_pinned_major_still_ships_a_compiler_api() -> None:
    """TypeScript 7 is the native port: its npm package exports `version` and
    nothing else, so the parser this lane calls does not exist there. The bump
    is a rewrite rather than a version change, and Dependabot raises majors as
    standalone PRs precisely so a human decides one. Failing here says which
    decision is owed; without it the failure is an unexplained parse error."""
    declared = json.loads(_read(_PACKAGE_JSON))["devDependencies"]["typescript"]

    assert declared.startswith("5."), (
        f"typescript is pinned to {declared}; the lane calls `ts.createSourceFile`,"
        " which the 5.x compiler exports and the 7.x native port does not."
        " Moving off 5.x means porting tests/support/parse_typescript.mjs to the"
        " new API, not just taking the bump"
    )


def test_ci_runs_the_lane_where_the_compiler_exists() -> None:
    """A lane nothing runs is a lane that reports on nothing."""
    job = _code_samples_job()

    assert "npm ci" in job, "the job does not install the pinned compiler"
    assert _LANE in job, f"the job does not run {_LANE}"


def test_ci_turns_a_skipped_lane_into_a_failure() -> None:
    """This is the assertion the whole file exists for. Without the variable a
    broken install skips the lane and the job still reports success — the exact
    shape of green-over-unchecked this gate is here to prevent."""
    job = _code_samples_job()

    assert "REQUIRE_SAMPLE_LANES" in job, (
        "the job does not set REQUIRE_SAMPLE_LANES, so a missing parser"
        f" skips a lane in {_LANE} and the job passes anyway"
    )
    # The variable does nothing on its own. What enforces it is a hook that
    # fails any skip in that module while it is set — the half a contributor
    # deleting a "weird" conftest would take with them.
    enforcement = _read(_REPO_ROOT / "tests" / "skills" / "conftest.py")
    assert "REQUIRE_SAMPLE_LANES" in enforcement, (
        "nothing reads REQUIRE_SAMPLE_LANES, so setting it in CI is decoration"
        " and a skipped lane still reports success"
    )


def test_sample_pipes_name_their_encoding() -> None:
    """A bare `text=True` encodes subprocess input with the platform default.

    That is cp1252 on a Windows runner, so a sample containing an arrow or an
    accent raises before the parser sees it and the lane reports valid content as
    malformed — the one outcome these lanes must never produce. It is invisible
    on a UTF-8 machine, which is why it reached CI. Asserted on the source
    because the alternative is re-learning it from a red Windows job each time a
    subprocess call is added.
    """
    lane = _read(_REPO_ROOT / _LANE)
    definition = '_TEXT_UTF8 = {"text": True, "encoding": "utf-8"}'

    assert definition in lane, "the lanes no longer define one UTF-8 pipe setting"
    # Matched as an argument rather than anywhere the characters appear, and in
    # both shapes a call can take: inline after `(` or `,`, and alone on its own
    # line in a wrapped call. Scanning whole lines flagged the comment explaining
    # this rule — a guard owning more text than its rule — and matching only the
    # inline shape then missed the wrapped call, which is the same error with the
    # sign flipped. Comments are excluded outright; prose about the rule is not
    # a violation of it.
    argument = re.compile(r"(?:[(,]\s*|^\s*)text=True\b")
    bare = [
        line.strip()
        for line in lane.splitlines()
        if not line.strip().startswith("#") and argument.search(line)
    ]
    assert not bare, (
        "these subprocess calls take the platform's default encoding instead of"
        " UTF-8, so a non-ASCII sample fails on a Windows runner:\n" + "\n".join(bare)
    )


@pytest.mark.parametrize("declaration", ["AGENTS.md", "CONTRIBUTING.md"])
def test_declarations_state_the_template_marker(declaration: str) -> None:
    """An author who has not read the lane's source has to learn the exemption
    somewhere other than a red build. The marker is the one part of this gate a
    contributor has to type, so a surface that describes authoring samples and
    omits it teaches the failure rather than the convention."""
    text = _read(_REPO_ROOT / declaration)

    assert "template" in text and "```bash template" in text, (
        f"{declaration} does not show the ```bash template marker, so the only"
        " way to discover it is to trip the parser"
    )


@pytest.mark.parametrize("path_filter", ["**/*.mjs", "requirements-test.txt", "package-lock.json"])
def test_push_filter_covers_the_lane_inputs(path_filter: str) -> None:
    """Absent from `paths:`, a push touching only that input skips the job.

    Matched as a list item with optional quoting: YAML accepts `- package.json`
    and `- "package.json"` alike, and which one is written is not this rule.
    """
    entry = re.compile(
        rf"""^\s*-\s*(?P<q>["']?){re.escape(path_filter)}(?P=q)\s*$""", re.MULTILINE
    )

    assert entry.search(_read(_LINT_WORKFLOW)), (
        f"{path_filter} is not in lint.yml's push paths: filter; a push touching"
        " only that file would skip the job it is an input to"
    )
