"""JSON Schema and content-guard tests for git-toolkit references/.

Generic link/pointer resolution across the skill tree lives in the fleet-wide
suite (`tests/skills/test_structure_all.py`); what stays here are the
contracts unique to this skill: the review-output NDJSON schema (validity,
prose agreement, worked-example conformance), the untrusted-content guard
wiring on ingestion capabilities, and the shared-reference wiring for the
force-push-impact and pr-input-guards blocks (each block lives in exactly one
reference; consumers link it and never restate it).
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest


def test_review_output_schema_is_valid_json(references_dir: Path) -> None:
    schema_path = references_dir / "review-output.schema.json"
    assert schema_path.is_file(), "review-output.schema.json not found"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    assert isinstance(schema, dict)
    assert schema.get("type") == "object"
    assert "properties" in schema
    assert "required" in schema
    # Top-level required must be a subset of declared properties.
    declared = set(schema["properties"].keys())
    required = set(schema["required"])
    assert required.issubset(declared), (
        f"required fields not in properties: {required - declared}"
    )


def test_review_output_schema_declares_recognized_draft(
    references_dir: Path,
) -> None:
    schema = json.loads((references_dir / "review-output.schema.json").read_text(encoding="utf-8"))
    uri = schema.get("$schema", "")
    recognized = (
        "https://json-schema.org/draft/2020-12/schema",
        "https://json-schema.org/draft/2019-09/schema",
        "http://json-schema.org/draft-07/schema#",
    )
    assert uri in recognized, f"unrecognized $schema URI: {uri!r}"


def test_review_output_schema_result_enum_matches_prose(
    references_dir: Path,
) -> None:
    """The schema's `result` enum must match the values listed in the prose
    spec (review-output.md). Catches drift between the two."""
    schema = json.loads((references_dir / "review-output.schema.json").read_text(encoding="utf-8"))
    schema_enum = set(schema["properties"]["result"]["enum"])
    prose = (references_dir / "review-output.md").read_text(encoding="utf-8")
    prose_values = set(re.findall(r"`(PASS|MOSTLY-PASS|FAIL|N/A)`", prose))
    # The prose may use slightly different forms; require schema enum to be a
    # subset of what the prose mentions (prose can list more nuances).
    missing = schema_enum - prose_values
    assert not missing, (
        f"schema enum values not documented in review-output.md: {missing}"
    )


@pytest.mark.parametrize(
    "rule_id",
    [
        "imperative-mood",
        "subject-length",
        "body-wrap",
        "trailers-preserved",
    ],
)
def test_rule_id_matches_schema_pattern(rule_id: str, references_dir: Path) -> None:
    """Sanity-check the schema's rule pattern against canonical rule ids
    used in the prose docs."""
    schema = json.loads((references_dir / "review-output.schema.json").read_text(encoding="utf-8"))
    pattern = schema["properties"]["rule"]["pattern"]
    assert re.fullmatch(pattern, rule_id), (
        f"canonical rule id {rule_id!r} fails schema pattern {pattern!r}"
    )


def test_example_ndjson_matches_schema_invariants(references_dir: Path) -> None:
    """The worked example stream must exist and each line must satisfy the
    schema's core invariants (stdlib-only, no jsonschema dependency): required
    keys, the rule-id pattern, the result enum, scope->sha/ref requirements,
    and FAIL/MOSTLY-PASS->fix. Guards against drift between the example and
    the schema/prose."""
    example = references_dir / "review-output.example.ndjson"
    assert example.is_file(), "review-output.example.ndjson not found"
    schema = json.loads((references_dir / "review-output.schema.json").read_text(encoding="utf-8"))
    rule_pattern = schema["properties"]["rule"]["pattern"]
    result_enum = set(schema["properties"]["result"]["enum"])
    scope_enum = set(schema["properties"]["scope"]["enum"])

    problems: list[str] = []
    lines = [
        ln for ln in example.read_text(encoding="utf-8").splitlines() if ln.strip()
    ]
    assert lines, "example stream is empty"
    for i, line in enumerate(lines, start=1):
        try:
            obj = json.loads(line)
        except json.JSONDecodeError as exc:
            problems.append(f"line {i}: invalid JSON ({exc})")
            continue
        for key in ("rule", "result", "scope"):
            if key not in obj:
                problems.append(f"line {i}: missing required key {key!r}")
        if "rule" in obj and not re.fullmatch(rule_pattern, obj["rule"]):
            problems.append(f"line {i}: rule {obj['rule']!r} fails pattern")
        if "result" in obj and obj["result"] not in result_enum:
            problems.append(f"line {i}: result {obj['result']!r} not in enum")
        if "scope" in obj and obj["scope"] not in scope_enum:
            problems.append(f"line {i}: scope {obj['scope']!r} not in enum")
        if obj.get("scope") == "commit" and "sha" not in obj:
            problems.append(f"line {i}: scope=commit requires sha")
        if obj.get("scope") in {"branch", "range", "pr"} and "ref" not in obj:
            problems.append(f"line {i}: scope={obj.get('scope')} requires ref")
        if obj.get("result") in {"FAIL", "MOSTLY-PASS"} and "fix" not in obj:
            problems.append(f"line {i}: result={obj['result']} requires fix")
    assert not problems, "example NDJSON violates schema invariants:\n" + "\n".join(problems)


# Capabilities that fetch untrusted third-party GitHub content (PR/issue/comment
# bodies, review threads, CI logs, fork diffs, contributor PR metadata) and feed
# it into verdicts, drafts, or proposed commands. Each must link the
# untrusted-content guard so the indirect-prompt-injection defense (Snyk W011)
# cannot be silently dropped when a capability is edited.
INGESTION_CAPABILITIES = [
    "pr-description-sync",
    "pr-checks-summary",
    "pr-conversation-resolve",
    "pr-link-issues",
    "pr-description-write",
    "release-notes",
    "merge-readiness",
    "commit-message",
]


def test_untrusted_content_reference_exists(references_dir: Path) -> None:
    assert (references_dir / "untrusted-content.md").is_file(), (
        "references/untrusted-content.md not found"
    )


@pytest.mark.parametrize("cap_name", INGESTION_CAPABILITIES)
def test_ingestion_capabilities_link_untrusted_content_guard(
    cap_name: str, capabilities_dir: Path
) -> None:
    """Every untrusted-content-ingesting capability must reference the guard at
    `../../references/untrusted-content.md`. This converts the platform finding
    (Snyk W011, indirect prompt injection) into a tested invariant."""
    cap_md = capabilities_dir / cap_name / "capability.md"
    assert cap_md.is_file(), f"{cap_name}/capability.md not found"
    text = cap_md.read_text(encoding="utf-8")
    assert "../../references/untrusted-content.md" in text, (
        f"{cap_name} ingests untrusted content but does not link "
        "../../references/untrusted-content.md (untrusted-content guard)"
    )


# Capabilities whose proposals rewrite history that may exist on a remote —
# amend, reword, squash, fixup-squash, body reflow. Each must link the shared
# force-push-impact reference (buckets, detection recipes, output block,
# --force-with-lease surfacing policy) instead of restating any of it.
FORCE_PUSH_CONSUMERS = [
    "commit-message",
    "commit-amend-message",
    "commit-body-reflow",
    "commit-fixup",
    "rebase-cleanup",
]

# GitHub-side capabilities per the SKILL.md scope legend. Each must run the
# standard input-guard sequence by linking the shared pr-input-guards
# reference, declaring only its deviations inline.
GITHUB_SIDE_CAPABILITIES = [
    "pr-description-write",
    "pr-description-sync",
    "pr-link-issues",
    "pr-checks-summary",
    "pr-conversation-resolve",
    "merge-readiness",
    "merge-execute",
]

# The canonical Force-Push Impact block's first line, verbatim from
# force-push-impact.md — used to prove the template has exactly one home.
_IMPACT_TEMPLATE_LINE = "Force-Push Impact: <none / mild / high>"


def test_force_push_impact_reference_is_the_single_home(references_dir: Path) -> None:
    """force-push-impact.md must exist and carry the load-bearing content the
    lift moved into it: the three buckets, the canonical output block, the
    stale tracking-refs caveat, and the guard pointers (untrusted-content for
    the review-anchor read, harness-safety-nets for proposal phrasing)."""
    ref = references_dir / "force-push-impact.md"
    assert ref.is_file(), "references/force-push-impact.md not found"
    text = ref.read_text(encoding="utf-8")
    for needle in (
        _IMPACT_TEMPLATE_LINE,
        "Never pushed",
        "Pushed, no review anchors",
        "Pushed and review-anchored",
        "git branch -r --contains",
        "--force-with-lease",
        "untrusted-content.md",
        "harness-safety-nets.md",
    ):
        assert needle in text, f"force-push-impact.md missing: {needle!r}"


def test_pr_input_guards_reference_is_the_single_home(references_dir: Path) -> None:
    """pr-input-guards.md must exist and cover the full guard sequence the
    GitHub-side capabilities used to restate: forge detection, PR resolution,
    state guard, bot guard, gh-auth handling, untrusted-content pointer."""
    ref = references_dir / "pr-input-guards.md"
    assert ref.is_file(), "references/pr-input-guards.md not found"
    text = ref.read_text(encoding="utf-8")
    for needle in (
        "forge-adapters.md",
        "gh pr list --head",
        "MERGED",
        "bot-signatures.md",
        "gh auth login",
        "untrusted-content.md",
    ):
        assert needle in text, f"pr-input-guards.md missing: {needle!r}"


@pytest.mark.parametrize("cap_name", FORCE_PUSH_CONSUMERS)
def test_history_rewriters_link_force_push_impact(
    cap_name: str, capabilities_dir: Path
) -> None:
    text = (capabilities_dir / cap_name / "capability.md").read_text(encoding="utf-8")
    assert "../../references/force-push-impact.md" in text, (
        f"{cap_name} rewrites history but does not link "
        "../../references/force-push-impact.md"
    )


@pytest.mark.parametrize("cap_name", GITHUB_SIDE_CAPABILITIES)
def test_github_side_capabilities_link_pr_input_guards(
    cap_name: str, capabilities_dir: Path
) -> None:
    text = (capabilities_dir / cap_name / "capability.md").read_text(encoding="utf-8")
    assert "../../references/pr-input-guards.md" in text, (
        f"{cap_name} is GitHub-side but does not link "
        "../../references/pr-input-guards.md"
    )


def test_no_capability_restates_the_impact_template(capabilities_dir: Path) -> None:
    """The canonical output block lives only in force-push-impact.md —
    consumers reference it, never restate it (G1 acceptance criterion)."""
    offenders = [
        cap.parent.name
        for cap in sorted(capabilities_dir.glob("*/capability.md"))
        if _IMPACT_TEMPLATE_LINE in cap.read_text(encoding="utf-8")
    ]
    assert not offenders, (
        f"capabilities restate the Force-Push Impact template: {offenders}"
    )


def test_no_capability_restates_pr_resolution(capabilities_dir: Path) -> None:
    """The PR resolution recipe (`gh pr list --head`) lives only in
    pr-input-guards.md — a capability spelling it out again is restating the
    guard block."""
    offenders = [
        cap.parent.name
        for cap in sorted(capabilities_dir.glob("*/capability.md"))
        if "gh pr list --head" in cap.read_text(encoding="utf-8")
    ]
    assert not offenders, (
        f"capabilities restate the PR resolution recipe: {offenders}"
    )


def test_no_cross_capability_step_citations(capabilities_dir: Path) -> None:
    """The fleet-wide suite kills sibling *path* references; this guards the
    path-less variant that motivated G1 — one capability citing another's
    numbered step (e.g. \"commit-message Step 5\") as its spec."""
    own_names = {p.name for p in capabilities_dir.iterdir() if p.is_dir()}
    pattern = re.compile(
        r"`?(" + "|".join(re.escape(n) for n in sorted(own_names)) + r")`?('s)? [Ss]tep \w+"
    )
    offenders: list[str] = []
    for cap in sorted(capabilities_dir.glob("*/capability.md")):
        for lineno, line in enumerate(cap.read_text(encoding="utf-8").splitlines(), start=1):
            m = pattern.search(line)
            if m and m.group(1) != cap.parent.name:
                offenders.append(f"{cap.parent.name}:{lineno} cites {m.group(0)!r}")
    assert not offenders, "cross-capability step citations:\n" + "\n".join(offenders)
