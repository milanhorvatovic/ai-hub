"""Holds the fleet's context cost against a committed baseline.

The numbers themselves are reported, not gated — how much a skill may grow is a
judgment nobody has data for yet. What blocks is the baseline going stale: a PR
that changes a skill's cost and leaves the recorded figure alone would make
every later delta a comparison against a fossil, which is the failure this whole
measurement exists to end. The same split R4 uses for the description corpora,
where the scores advise and the freshness check blocks.

So a failure here is not "the skill got too big". It is "the recorded cost no
longer describes the tree", and the fix is to refresh and review the diff.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests.support.context_cost import baseline_for, lf_bytes, measure

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
        key: f"{recorded[key]} -> {value}"
        for key, value in measured.items()
        if recorded.get(key) != value
    }
    assert not drift, (
        f"{name}'s recorded context cost is stale: {drift}\n"
        f"Refresh with {REFRESH}, then review the deltas in the diff — that "
        "review is the point of the number."
    )


def test_counts_ignore_the_line_endings_the_checkout_chose(tmp_path: Path) -> None:
    """A CRLF checkout must report what an LF checkout reports.

    `.gitattributes` checks markdown out native, so the Windows legs of the
    matrix read every file a byte per line heavier. Raw counts would make the
    platform the largest mover in the trend, so the guard is here rather than in
    a comment on the normalization.
    """
    skill = tmp_path / "sample"
    (skill / "references").mkdir(parents=True)
    (skill / "SKILL.md").write_text(
        "---\nname: sample\ndescription: one\n---\n\nSee `references/one.md`.\n",
        encoding="utf-8",
    )
    (skill / "references" / "one.md").write_text("# One\n\nBody line.\n", encoding="utf-8")

    as_lf = measure(skill)
    for path in sorted(skill.rglob("*.md")):
        path.write_bytes(path.read_bytes().replace(b"\n", b"\r\n"))

    assert measure(skill) == as_lf


def test_frontmatterless_files_cost_nothing_to_discover(tmp_path: Path) -> None:
    """Discovery bills frontmatter only, so a reference adds load and no more."""
    skill = tmp_path / "sample"
    (skill / "references").mkdir(parents=True)
    (skill / "SKILL.md").write_text(
        "---\nname: sample\n---\n\nSee `references/one.md`.\n", encoding="utf-8"
    )
    reference = skill / "references" / "one.md"
    reference.write_text("# One\n", encoding="utf-8")

    cost = measure(skill)
    assert cost.discovery_bytes == cost.skill_md_bytes - len("\nSee `references/one.md`.\n")
    assert cost.load_bytes == cost.skill_md_bytes + lf_bytes(reference)


def test_baseline_file_matches_what_the_generator_writes(baseline) -> None:
    """The committed file is the generator's output, not a hand-edited copy."""
    assert baseline == baseline_for(SKILLS_ROOT), (
        f"committed baseline differs from a fresh computation; refresh with {REFRESH}"
    )
