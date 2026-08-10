"""Holds the fleet's context cost against a committed baseline.

The numbers themselves are reported, not gated — how much a skill may grow is a
judgment nobody has data for yet. What blocks is the baseline going stale: a PR
that changes a skill's cost and leaves the recorded figure alone would make
every later delta a comparison against a fossil, which is the failure this whole
measurement exists to end. The same split the description corpora use, where the
evaluator's precision and recall scores are advisory and the corpus-hash
freshness check blocks.

So a failure here is not "the skill got too big". It is "the recorded cost no
longer describes the tree", and the fix is to refresh and review the diff.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests.support.context_cost import frontmatter_bytes, lf_bytes, measure

REPO_ROOT = Path(__file__).resolve().parents[2]
SKILLS_ROOT = REPO_ROOT / "skills"
BASELINE_PATH = REPO_ROOT / "tests" / "skills" / "context-cost-baseline.json"

REFRESH = "./venv/bin/python -m tests.support.context_cost"

SKILL_NAMES = sorted(path.parent.name for path in SKILLS_ROOT.glob("*/SKILL.md"))


@pytest.fixture(scope="module")
def baseline() -> dict[str, dict[str, int]]:
    return json.loads(BASELINE_PATH.read_text(encoding="utf-8"))


def test_baseline_covers_exactly_the_shipped_skills(baseline) -> None:
    assert sorted(baseline) == SKILL_NAMES, (
        f"baseline and skills/ disagree on which skills exist; refresh with {REFRESH}"
    )


@pytest.mark.parametrize("name", SKILL_NAMES)
def test_recorded_cost_still_describes_the_tree(name: str, baseline) -> None:
    recorded = baseline.get(name)
    assert recorded is not None, f"{name} has no recorded cost; refresh with {REFRESH}"

    measured = measure(SKILLS_ROOT / name).as_baseline()
    drift = {
        key: f"{recorded.get(key)} -> {measured.get(key)}"
        for key in recorded.keys() | measured.keys()
        if recorded.get(key) != measured.get(key)
    }
    assert not drift, (
        f"{name}'s recorded context cost is stale: {drift}\n"
        f"Refresh with {REFRESH}, then review the deltas in the diff — that "
        "review is the point of the number."
    )


@pytest.mark.parametrize(
    "document", ["AGENTS.md", "CONTRIBUTING.md", "docs/adding-a-skill.md"], ids=lambda p: Path(p).name
)
def test_the_contributor_docs_name_the_refresh_command(document: str) -> None:
    """A gate nobody declared is a gate contributors meet as a CI failure.

    Adding a skill now fails this suite until the baseline records it, which is
    a wiring step like the manifest and the corpus — so all three declaration
    surfaces name the command the failure message names. Pinned because they
    drift apart silently: the gate keeps working while the docs stop describing
    it.
    """
    text = (REPO_ROOT / document).read_text(encoding="utf-8")

    assert BASELINE_PATH.name in text
    assert REFRESH.removeprefix("./") in text


def test_the_runbook_lists_the_baseline_as_a_wiring_step() -> None:
    """In the checklist, not only in the prose below it.

    Someone adding a skill reads the table and works down it; a step that exists
    only in a later section is a step they meet as a failing test. Asserting the
    filename appears somewhere in the document does not catch that — the section
    alone satisfies it — so this looks for the row.
    """
    runbook = (REPO_ROOT / "docs" / "adding-a-skill.md").read_text(encoding="utf-8")
    rows = [line for line in runbook.splitlines() if line.startswith("|")]

    listed = [
        row for row in rows if BASELINE_PATH.name in row and "test_context_cost.py" in row
    ]
    assert listed, "the wiring checklist has no row for the context-cost baseline"


def test_counts_ignore_the_line_endings_the_checkout_chose(tmp_path: Path) -> None:
    """A CRLF checkout must report what an LF checkout reports.

    `.gitattributes` checks markdown out native, so the Windows legs of the
    matrix read every file a byte per line heavier. Raw counts would make the
    platform the largest mover in the trend, so the guard is here rather than in
    a comment on the normalization.

    Every fixture in this module writes bytes rather than text: `write_text`
    translates `\n` to `\r\n` on Windows, so a "LF" fixture built that way is
    already CRLF there and converting it again yields `\r\r\n`. That corrupts
    the frontmatter delimiter and fails this test for a reason that has nothing
    to do with the code under it — which is exactly what it did on the first CI
    run. A suite about byte counts cannot let the platform choose its input.
    """
    skill = tmp_path / "sample"
    (skill / "references").mkdir(parents=True)
    (skill / "SKILL.md").write_bytes(
        b"---\nname: sample\ndescription: one\n---\n\nSee `references/one.md`.\n"
    )
    (skill / "references" / "one.md").write_bytes(b"# One\n\nBody line.\n")

    as_lf = measure(skill)
    for path in sorted(skill.rglob("*.md")):
        path.write_bytes(path.read_bytes().replace(b"\n", b"\r\n"))

    assert measure(skill) == as_lf


def test_a_reached_binary_keeps_every_byte_it_has(tmp_path: Path) -> None:
    """Normalization is for line endings, and a binary has none.

    The markdown-link collector accepts any relative target, so an image or a
    PDF can be reached. Rewriting `\\r\\n` inside one would report it smaller
    than it loads, by however many of those pairs its payload happens to hold —
    silently, since nothing else would disagree. Latent: nothing links a binary
    today, which is why the case is stated rather than waited for.
    """
    skill = tmp_path / "sample"
    (skill / "references").mkdir(parents=True)
    (skill / "SKILL.md").write_bytes(b"---\nname: sample\n---\n\nSee [chart](references/c.png).\n")
    binary = skill / "references" / "c.png"
    binary.write_bytes(b"\x89PNG\r\n\x1a\n\r\n\r\n")

    cost = measure(skill)
    assert lf_bytes(binary) == len(binary.read_bytes())
    assert cost.load_bytes == cost.skill_md_bytes + len(binary.read_bytes())


def test_frontmatterless_files_cost_nothing_to_discover(tmp_path: Path) -> None:
    """Discovery bills frontmatter only, so a reference adds load and no more."""
    skill = tmp_path / "sample"
    (skill / "references").mkdir(parents=True)
    router = skill / "SKILL.md"
    router.write_bytes(b"---\nname: sample\n---\n\nSee `references/one.md`.\n")
    reference = skill / "references" / "one.md"
    reference.write_bytes(b"# One\n")

    cost = measure(skill)
    assert frontmatter_bytes(reference) == 0
    assert cost.discovery_bytes == frontmatter_bytes(router)
    assert cost.load_bytes == cost.skill_md_bytes + lf_bytes(reference)


def test_discovery_bills_a_capability_the_router_never_reaches(tmp_path: Path) -> None:
    """An orphaned capability costs discovery but not load.

    Whoever scans the directory reads its frontmatter whether the router points
    at it or not, so discovery has to come from the tree rather than the walk.
    Computing it from the walk gives the same answer on a valid fleet and stops
    being right the moment the orphan checks do — this is the case that
    separates the two.
    """
    skill = tmp_path / "sample"
    (skill / "capabilities" / "orphan").mkdir(parents=True)
    (skill / "SKILL.md").write_bytes(b"---\nname: sample\n---\n\nNo rows.\n")
    orphan = skill / "capabilities" / "orphan" / "capability.md"
    orphan.write_bytes(b"---\nname: orphan\n---\n\nUnrouted.\n")

    cost = measure(skill)
    assert cost.discovery_bytes == frontmatter_bytes(skill / "SKILL.md") + frontmatter_bytes(orphan)
    assert cost.files == 1
    assert cost.load_bytes == cost.skill_md_bytes


def test_neither_number_bills_the_directories_a_skill_only_ships(tmp_path: Path) -> None:
    """Assets and scripts are handed to a tool, never pulled into context.

    Load has excluded them from the start; discovery reads the directory rather
    than the walk and has to exclude them by the same rule, or a frontmatter
    block under `assets/` would be billed for a scan that never looks there.
    Latent today — the one shipped file in that position carries no frontmatter
    — so the case is stated here rather than left to the first one that does.
    """
    skill = tmp_path / "sample"
    (skill / "assets").mkdir(parents=True)
    (skill / "SKILL.md").write_bytes(b"---\nname: sample\n---\n\nSee `assets/sheet.md`.\n")
    (skill / "assets" / "sheet.md").write_bytes(b"---\nname: sheet\n---\n\nData.\n")

    cost = measure(skill)
    assert cost.discovery_bytes == frontmatter_bytes(skill / "SKILL.md")
    assert cost.load_bytes == cost.skill_md_bytes
    assert cost.files == 1
