"""Shape guards for the description-evaluation corpora under tests/skill-corpus/.

Each shipped skill carries a corpus of positive prompts (should activate the
skill) and negative prompts (should activate a sibling or nothing), encoding
the routing boundaries between the fleet's descriptions. Scoring runs in the
`description-eval` workflow through the pinned skill-system-foundry evaluator;
that workflow also owns `description_sha256` freshness, because recomputing the
hash requires the foundry's frontmatter folding. This suite owns everything
checkable from the corpus files alone, so a malformed corpus fails the plain
pytest run instead of surfacing only in the eval workflow.

The shape rules mirror the FAIL-level corpus rules of the foundry evaluator
(`evaluate_descriptions.py`), plus deliberately stricter house rules: the
per-side floor is the foundry's *recommended* count (8, not the minimum 4) so
the eval never warns, prompts must be unique across the whole corpus set (the
foundry only warns when a positive is shared between competing targets),
leading-bigram diversity fails here where the foundry only warns, and the
backfilled `description_sha256` is required rather than tolerated-absent.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SKILLS_ROOT = REPO_ROOT / "skills"
CORPUS_ROOT = REPO_ROOT / "tests" / "skill-corpus"

# Mirrors the `skill.description.evaluation` block of the foundry's
# scripts/lib/configuration.yaml; the pinned checkout in the description-eval
# workflow is authoritative.
MIN_PROMPTS_PER_SIDE = 8
MAX_PROMPT_CHARS = 2000
MIN_LEADING_BIGRAM_RATIO = 0.6

REQUIRED_KEYS = {"target", "kind", "positive", "negative"}
OPTIONAL_KEYS = {"description_sha256", "min_precision", "min_recall"}

SKILL_NAMES = sorted(
    path.parent.name for path in SKILLS_ROOT.glob("*/SKILL.md")
)
CORPUS_DIRS = sorted(
    path for path in CORPUS_ROOT.iterdir() if path.is_dir()
) if CORPUS_ROOT.is_dir() else []


def _corpus(name: str) -> dict:
    path = CORPUS_ROOT / name / "skill.json"
    if not path.is_file():
        pytest.fail(f"missing corpus file: {path.relative_to(REPO_ROOT)}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        pytest.fail(f"invalid JSON in {path.relative_to(REPO_ROOT)}: {exc}")


def _prompts(data: dict, side: str) -> list[str]:
    value = data.get(side)
    assert isinstance(value, list) and all(isinstance(p, str) for p in value), (
        f"'{side}' must be a list of strings"
    )
    return value


def _has_control_chars(text: str) -> bool:
    return any(ord(c) < 0x20 or 0x7F <= ord(c) < 0xA0 for c in text)


@pytest.mark.parametrize("skill", SKILL_NAMES)
def test_every_skill_has_a_corpus(skill: str) -> None:
    assert (CORPUS_ROOT / skill / "skill.json").is_file(), (
        f"skills/{skill}/ has no corpus at tests/skill-corpus/{skill}/skill.json; "
        "every shipped description needs its activation corpus"
    )


@pytest.mark.parametrize("corpus_dir", CORPUS_DIRS, ids=lambda p: p.name)
def test_every_corpus_names_a_shipped_skill(corpus_dir: Path) -> None:
    assert corpus_dir.name in SKILL_NAMES, (
        f"tests/skill-corpus/{corpus_dir.name}/ does not match any skills/ directory"
    )
    assert (corpus_dir / "skill.json").is_file(), (
        f"tests/skill-corpus/{corpus_dir.name}/ is missing skill.json"
    )


@pytest.mark.parametrize("skill", SKILL_NAMES)
def test_corpus_keys_and_identity(skill: str) -> None:
    data = _corpus(skill)
    assert isinstance(data, dict), "top-level JSON value must be an object"
    missing = REQUIRED_KEYS - data.keys()
    assert not missing, f"missing required keys: {sorted(missing)}"
    unknown = {
        key for key in data
        if not key.startswith("_") and key not in REQUIRED_KEYS | OPTIONAL_KEYS
    }
    assert not unknown, f"unknown top-level keys: {sorted(unknown)}"
    assert data["target"] == skill, "'target' must match the corpus directory name"
    assert data["kind"] == "skill"


@pytest.mark.parametrize("skill", SKILL_NAMES)
@pytest.mark.parametrize("side", ["positive", "negative"])
def test_prompts_are_clean(skill: str, side: str) -> None:
    prompts = _prompts(_corpus(skill), side)
    assert len(prompts) >= MIN_PROMPTS_PER_SIDE, (
        f"'{side}' has {len(prompts)} prompts; the house floor is "
        f"{MIN_PROMPTS_PER_SIDE} (the foundry's recommended count)"
    )
    for prompt in prompts:
        assert prompt.strip(), f"empty or whitespace-only prompt in '{side}'"
        assert len(prompt) <= MAX_PROMPT_CHARS, f"over-length prompt in '{side}': {prompt!r}"
        assert not _has_control_chars(prompt), f"control characters in '{side}': {prompt!r}"
    stripped = [p.strip() for p in prompts]
    assert len(set(stripped)) == len(stripped), f"duplicate prompts within '{side}'"


@pytest.mark.parametrize("skill", SKILL_NAMES)
def test_no_prompt_contradicts_itself(skill: str) -> None:
    data = _corpus(skill)
    both = {p.strip() for p in _prompts(data, "positive")} & {
        p.strip() for p in _prompts(data, "negative")
    }
    assert not both, f"prompts on both sides: {sorted(both)}"


@pytest.mark.parametrize("skill", SKILL_NAMES)
def test_leading_bigram_diversity(skill: str) -> None:
    data = _corpus(skill)
    prompts = _prompts(data, "positive") + _prompts(data, "negative")
    bigrams = {" ".join(p.lower().split()[:2]) for p in prompts}
    ratio = len(bigrams) / len(prompts)
    assert ratio >= MIN_LEADING_BIGRAM_RATIO, (
        f"leading-bigram diversity {ratio:.2f} is below "
        f"{MIN_LEADING_BIGRAM_RATIO} — vary the prompt openings"
    )


@pytest.mark.parametrize("skill", SKILL_NAMES)
def test_description_hash_is_recorded(skill: str) -> None:
    sha = _corpus(skill).get("description_sha256")
    assert isinstance(sha, str) and len(sha) == 64 and all(
        c in "0123456789abcdef" for c in sha
    ), (
        "description_sha256 must be the backfilled lowercase hex digest; "
        "run the foundry evaluator with --backfill-hash after a description change"
    )


def test_no_prompt_shared_across_corpora() -> None:
    owners: dict[str, list[str]] = {}
    for skill in SKILL_NAMES:
        data = _corpus(skill)
        for side in ("positive", "negative"):
            for prompt in _prompts(data, side):
                owners.setdefault(prompt.strip(), []).append(f"{skill}/{side}")
    shared = {p: where for p, where in owners.items() if len(where) > 1}
    assert not shared, f"prompts appear in more than one corpus: {shared}"
