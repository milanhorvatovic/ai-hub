"""Content contracts for the behavior-coach skill.

Guards the load-bearing promises the router makes: the six-stage pipeline,
the prompt-level-only scope boundary, and the honest-limits requirement on
produced skills. Wording may evolve; these anchors must not silently vanish.
"""

from __future__ import annotations

from pathlib import Path

import pytest

_STAGES = [
    "Scope",
    "Capture",
    "Baseline",
    "Extract",
    "Author",
    "Pressure-test",
]


def test_pipeline_lists_all_six_stages_in_order(skill_md: Path) -> None:
    text = skill_md.read_text(encoding="utf-8")
    positions = []
    for i, stage in enumerate(_STAGES, start=1):
        needle = f"{i}. {stage}"
        pos = text.find(needle)
        assert pos != -1, f"pipeline stage `{needle}` missing from SKILL.md"
        positions.append(pos)
    assert positions == sorted(positions), "pipeline stages out of order"


def test_scope_boundary_forbids_training_transfer(skill_md: Path) -> None:
    """The skill is prompt-level only; the no-fine-tuning / no-training-data
    boundary is a policy anchor, not stylistic prose. Anchored inside the
    Scope boundaries section, because stray mentions elsewhere ("the target
    wasn't trained on") would keep a whole-file substring check green after
    the actual prohibitions were removed."""
    text = skill_md.read_text(encoding="utf-8")
    start = text.find("## Scope boundaries")
    assert start != -1, "Scope boundaries section missing from SKILL.md"
    end = text.find("\n## ", start + 1)
    section = text[start : end if end != -1 else len(text)]
    assert "does not fine-tune" in section, "no-fine-tuning boundary missing"
    assert "does not generate training datasets" in section, (
        "training-data boundary missing"
    )


@pytest.mark.parametrize(
    "filename",
    ["SKILL.md", "references/portability-rules.md", "references/worked-example.md"],
)
def test_honest_limits_note_is_required(skill_root: Path, filename: str) -> None:
    """Produced skills must declare what they do NOT transfer; the
    requirement must survive in the contract, the authoring rules, and the
    worked example alike."""
    text = (skill_root / filename).read_text(encoding="utf-8")
    assert "honest-limits" in text, f"{filename} lost the honest-limits anchor"


def test_pressure_testing_names_the_three_critics(references_dir: Path) -> None:
    text = (references_dir / "pressure-testing.md").read_text(encoding="utf-8")
    for critic in ("Loophole hunter", "Dead-weight critic", "Format reviewer"):
        assert critic in text, f"critic `{critic}` missing from REFACTOR pass"


def test_delta_classes_are_stable(references_dir: Path) -> None:
    text = (references_dir / "delta-extraction.md").read_text(encoding="utf-8")
    for klass in ("PORTABLE", "PARTIAL", "NON-PORTABLE"):
        assert klass in text, f"delta class `{klass}` missing"
