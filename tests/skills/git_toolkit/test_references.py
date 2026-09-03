"""JSON Schema and content-guard tests for git-toolkit references/.

Generic link/pointer resolution across the skill tree lives in the fleet-wide
suite (`tests/skills/test_structure_all.py`); what stays here are the
contracts unique to this skill: the review-output NDJSON schema (validity,
prose agreement, worked-example conformance), the shared-reference wiring for
the force-push-impact, pr-input-guards, and forge-adapters blocks (each block
lives in exactly one reference; consumers link it and never restate it), and
the safety-wiring matrix — SKILL.md's "safety wiring is a checklist" principle
enforced as a test. Each safety reference (untrusted-content, secret-patterns,
bot-signatures, harness-safety-nets) has a maintained consumer-class list
below; every capability must appear in the classes that fit it, and a
completeness check forces new capabilities to declare their classes.
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
# cannot be silently dropped when a capability is edited. Membership is literal
# by decision: capabilities whose only third-party read is the Force-Push
# Impact enrichment (commit-body-reflow, commit-fixup, rebase-cleanup)
# carry their own link rather than relying on force-push-impact.md's guarded
# anchor-read, so this list needs no exemptions.
INGESTION_CAPABILITIES = [
    "pr-description",
    "pr-checks-summary",
    "pr-conversation-resolve",
    "pr-link-issues",
    "release-notes",
    "merge-readiness",
    "merge-execute",
    "commit-message",
    "commit-body-reflow",
    "commit-fixup",
    "rebase-cleanup",
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
    "commit-body-reflow",
    "commit-fixup",
    "rebase-cleanup",
]

# Forge-side capabilities per the SKILL.md scope legend. Each must run the
# standard input-guard sequence by linking the shared pr-input-guards
# reference, declaring only its deviations inline.
FORGE_SIDE_CAPABILITIES = [
    "pr-description",
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
    forge-side capabilities used to restate: forge detection and command-lane
    selection, PR resolution, state guard, bot guard, auth handling,
    untrusted-content pointer."""
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


@pytest.mark.parametrize("cap_name", FORGE_SIDE_CAPABILITIES)
def test_forge_side_capabilities_link_pr_input_guards(
    cap_name: str, capabilities_dir: Path
) -> None:
    text = (capabilities_dir / cap_name / "capability.md").read_text(encoding="utf-8")
    assert "../../references/pr-input-guards.md" in text, (
        f"{cap_name} is forge-side but does not link "
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


def test_forge_adapter_mapping_is_the_single_home(
    references_dir: Path, capabilities_dir: Path
) -> None:
    """The alternative-lane mapping (GitLab `glab`, Forgejo `tea`, the
    Bitbucket lane's `bkt` and REST forms) lives only in forge-adapters.md.
    Capability bodies express each operation once, with the gh command as the
    GitHub worked example, and route other forges through the adapter table —
    naming an alternative CLI or the Bitbucket API host inline would fork the
    mapping."""
    adapters = (references_dir / "forge-adapters.md").read_text(encoding="utf-8")
    for marker in ("glab", "tea", "bkt", "api.bitbucket.org"):
        assert re.search(rf"\b{re.escape(marker)}\b", adapters), (
            f"forge-adapters.md no longer mentions {marker!r} — every lane's "
            "mapping lives in this file"
        )
    pattern = re.compile(r"\b(glab|tea|bkt)\b|api\.bitbucket\.org")
    offenders = [
        f"{cap.parent.name}:{lineno}: {line.strip()}"
        for cap in sorted(capabilities_dir.glob("*/capability.md"))
        for lineno, line in enumerate(
            cap.read_text(encoding="utf-8").splitlines(), start=1
        )
        if pattern.search(line)
    ]
    assert not offenders, (
        "capability bodies name an alternative forge lane (CLI or Bitbucket "
        "API host) — the mapping's single home is forge-adapters.md:\n"
        + "\n".join(offenders)
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


# Capabilities that draft text for publication — commit messages (including
# squash-message overrides in a surfaced merge command), PR bodies and body
# patches, review replies, release notes. Each must run the pre-publication
# secret scan; secret-patterns.md has no transitive carrier, so the link is
# always literal.
SECRET_SCAN_CAPABILITIES = [
    "commit-message",
    "commit-body-reflow",
    "rebase-cleanup",
    "pr-description",
    "pr-link-issues",
    "pr-conversation-resolve",
    "release-notes",
    "merge-execute",
]

# The audience guard's consumer class is the same one, derived rather than
# restated: SKILL.md defines a single "drafts text for publication" class whose
# members run both scans over the same text in the same pass. Two literal lists
# could drift apart, and the drift would read as a deliberate exemption — one
# guard covering less than the other with nothing saying why.
PUBLICATION_AUDIENCE_CAPABILITIES = SECRET_SCAN_CAPABILITIES

# Capabilities whose input guards decide "is this author a bot?" — to skip
# (format-mutating: a rewrite would be overwritten on the bot's next run), to
# mention-and-proceed (read-only carve-out), or to run the standard sequence's
# bot step undeviated (merge-execute). The catalog is reachable directly or
# through pr-input-guards.md, whose standard sequence includes the bot guard
# (asserted by test_pr_input_guards_reference_is_the_single_home).
BOT_GUARD_CAPABILITIES = [
    "commit-message",
    "commit-body-reflow",
    "commit-fixup",
    "rebase-cleanup",
    "release-notes",
    "merge-readiness",
    "merge-execute",
    "pr-description",
    "pr-link-issues",
    "pr-conversation-resolve",
    "pr-checks-summary",
]

# Capabilities that propose operations agent-harness classifiers routinely
# flag — force-push publishes, history rewrites, merge execution. Every
# history rewriter is by definition in this class, so the list is derived
# from FORCE_PUSH_CONSUMERS rather than restated. The intent/impact/recovery
# phrasing rules are reachable directly or through force-push-impact.md,
# whose proposal-phrasing section carries them (asserted by
# test_force_push_impact_reference_is_the_single_home).
FLAGGED_OPERATION_PROPOSERS = [*FORCE_PUSH_CONSUMERS, "merge-execute"]

# Capabilities in no safety class: they publish nothing and propose no
# flagged operation, and their only third-party exposure is sampling branch
# names to infer naming conventions — counted for prefix vocabulary and slug
# style, never carried into drafts as content — a deliberate, bounded
# exemption. A new capability lands either here or in the class lists above —
# test_every_capability_is_classified refuses unclassified capabilities.
UNCLASSIFIED_SAFE_CAPABILITIES = [
    "branch-name",
    "worktree-setup",
]


@pytest.mark.parametrize("cap_name", SECRET_SCAN_CAPABILITIES)
def test_publishing_capabilities_link_secret_patterns(
    cap_name: str, capabilities_dir: Path
) -> None:
    text = (capabilities_dir / cap_name / "capability.md").read_text(encoding="utf-8")
    assert "../../references/secret-patterns.md" in text, (
        f"{cap_name} drafts text for publication but does not link "
        "../../references/secret-patterns.md (pre-publication secret scan)"
    )


def test_publication_audience_reference_is_the_single_home(
    references_dir: Path,
) -> None:
    """publication-audience.md must exist and carry the detections consumers
    rely on: the contract, every pattern name, the WARN grade, and the
    registry id findings report under. Deleting a pattern to quiet a false
    positive fails here by name instead of removing a check silently."""
    ref = references_dir / "publication-audience.md"
    assert ref.is_file(), "references/publication-audience.md not found"
    text = ref.read_text(encoding="utf-8")
    for needle in (
        "diff-visible, publicly linkable, or defined",
        "definite_reference",
        "session_deixis",
        "track_code",
        "private_path",
        "foreign_repository",
        "foreign_branch",
        "`WARN`",
        "private-context-ref",
        "secret-patterns.md",
        # The declaration trust model: a change cannot supply the judge that
        # grades it, so this one is a security property rather than wording.
        "Read declarations from the base branch",
        # Severity has to survive the trip to each consumer, or a declaration
        # that raises a finding to `error` buys nothing at the surface that
        # actually publishes the text.
        "Every consumer passes the grade through",
        # The exemption is a sentence-level step because a lookahead can only
        # see forward: folding it back into the expressions would clear
        # "as discussed in #12" and keep warning about the spelling below.
        "sentence-level exemption",
        "See #12 for the plan",
        # Presence of a `#N` is not resolution: a dangling issue or an
        # intranet link looks like an antecedent and hands the reader nothing,
        # so the exemption has to verify rather than pattern-match.
        "Presence is not resolution",
        # A root-relative markdown destination matches the path expression and
        # is a public link, so it is resolved rather than matched — another
        # step the pattern cannot carry on its own.
        "as a link first",
    ):
        assert needle in text, f"publication-audience.md missing: {needle!r}"


@pytest.mark.parametrize("cap_name", PUBLICATION_AUDIENCE_CAPABILITIES)
def test_publishing_capabilities_link_publication_audience(
    cap_name: str, capabilities_dir: Path
) -> None:
    """The audience half of the pre-publication pass has no transitive carrier
    either, so every drafting capability links it literally — a body can be
    free of secrets and still unreadable to everyone but its author."""
    text = (capabilities_dir / cap_name / "capability.md").read_text(encoding="utf-8")
    assert "../../references/publication-audience.md" in text, (
        f"{cap_name} drafts text for publication but does not link "
        "../../references/publication-audience.md (pre-publication audience check)"
    )


# One string each pattern must match and one it must not. Literal on purpose:
# the catalog is consumed as raw text, so a pattern is only as good as its
# spelling in the file, and a compile-only check passes an over-escaped form
# that matches nothing real — the shape this test was written after.
AUDIENCE_PATTERN_PROBES = {
    # These two entries are candidate finders: the link/issue-reference
    # exemption is a sentence-level step, not part of the expression, so the
    # misses here are only what the pattern itself must never match. The
    # exemption has its own guard below.
    "definite_reference": (("as the plan says",), ("the retry cap is 3",)),
    "session_deixis": (
        ("as discussed, cap at 3",),
        ("the cap is 3", "per the diff", "per the API docs"),
    ),
    # The miss probe is a longer token, not an issue reference: `#482` never
    # matched the letter-prefixed pattern anyway, so probing one proves
    # nothing, while `HTTP2` is the real risk the lookbehind exists to stop.
    "track_code": (("finding Z9 covers it",), ("HTTP2 traffic only",)),
    # Three roots, one of them outside any home directory: the pattern claims
    # absolute paths, and a probe set drawn only from /Users and /home would
    # let it narrow back to a root list without anything going red.
    "private_path": (
        (
            r"see C:\Users\dev\notes.md",
            # Windows accepts either separator, and a UNC path opens with two
            # backslashes; a POSIX author picturing only `C:\` leaves both of
            # these ordinary spellings unflagged.
            "see C:/Users/dev/notes.md",
            r"see \\server\share\notes.md",
            "see /tmp/design.md",
            "see ~/notes.md",
            "see `/home/dev/plan.md`",
            # A path in a description is usually a flag or variable value, so
            # a delimiter list drawn from prose habits misses the common case.
            "run --config=/home/dev/plan.md",
            "HOME=~/workspace",
        ),
        ("see docs/adr/0001-x.md", "see https://example.com/x", "see `https://x.dev/a`"),
    ),
    # A relative path is a candidate, not a finding — the tree-and-diff
    # resolution decides. Both probes are candidates for that reason: the
    # existing one clears at the resolution step, which a regex cannot do,
    # while ordinary prose with a slash must never reach the step at all.
    "unresolved_relative_path": (
        ("see private-notes/plan.md", "see docs/adr/0001-x.md"),
        ("and/or both", "see /tmp/design.md", "see https://example.com/x"),
    ),
}


@pytest.mark.parametrize(
    ("pattern_name", "probes"), sorted(AUDIENCE_PATTERN_PROBES.items())
)
def test_audience_patterns_match_what_they_claim(
    pattern_name: str, probes: tuple[str, str], references_dir: Path
) -> None:
    text = (references_dir / "publication-audience.md").read_text(encoding="utf-8")
    catalog = dict(re.findall(r"^- `(\w+)` — `([^`]+)`", text, flags=re.MULTILINE))
    assert pattern_name in catalog, (
        f"publication-audience.md declares no regex for {pattern_name!r}"
    )
    expression = re.compile(catalog[pattern_name])
    hits, misses = probes
    for hit in hits:
        assert expression.search(hit), (
            f"{pattern_name} no longer matches {hit!r} — the guard has gone quiet"
        )
    for miss in misses:
        assert not expression.search(miss), (
            f"{pattern_name} matches {miss!r}, which is ordinary published text"
        )


def test_write_mode_authors_from_public_inputs(capabilities_dir: Path) -> None:
    """The input rule is the cheap half of the audience guard — it keeps
    private context out of the draft, where the scan can only catch it after
    the fact. It is prose, so nothing but this test stands between it and a
    tidy-up that deletes it as redundant with the scan."""
    text = (capabilities_dir / "pr-description" / "capability.md").read_text(
        encoding="utf-8"
    )
    for needle in (
        "Author from public inputs only",
        "does not enter the draft",
    ):
        assert needle in text, (
            "pr-description WRITE mode lost its public-inputs rule "
            f"({needle!r}) — the scan would become the only line"
        )


def test_merge_readiness_gate_covers_self_containment(capabilities_dir: Path) -> None:
    """The readiness gate delegates its description check to the SYNC
    workflow, and a dimension the delegate grades while the gate stays silent
    about it is a dimension that cannot block a merge — including a
    repository-declared `error`, which in a body-as-commit-message repo lands
    in permanent history on the way through."""
    text = (capabilities_dir / "merge-readiness" / "capability.md").read_text(
        encoding="utf-8"
    )
    assert "private-context-ref" in text, (
        "merge-readiness's description gate no longer names the "
        "self-containment dimension it delegates"
    )


def test_branch_name_bans_private_codes_in_the_slug(capabilities_dir: Path) -> None:
    """A branch name is published on push, so it carries the same defect the
    drafting capabilities scan for. It stays out of the audience consumer
    class — it drafts no prose and runs no scan — so this one line is the
    whole guard, and prose with nothing holding it is what rots first."""
    text = (capabilities_dir / "branch-name" / "capability.md").read_text(
        encoding="utf-8"
    )
    assert "private planning code in the slug" in text, (
        "branch-name lost its anti-pattern against private codes in a slug"
    )


def test_commit_message_review_table_grades_the_audience_rule(
    capabilities_dir: Path,
) -> None:
    """Scoped to the grading row rather than the file: the id appears in prose
    elsewhere, so a whole-file substring check stays green while the row that
    does the grading is deleted — a test describing a mutation it cannot
    detect."""
    text = (capabilities_dir / "commit-message" / "capability.md").read_text(
        encoding="utf-8"
    )
    row = next(
        (ln for ln in text.splitlines() if ln.startswith("| Publication audience |")),
        None,
    )
    assert row is not None, (
        "commit-message's REVIEW table lost its Publication audience row"
    )
    assert "`private-context-ref`" in row, (
        "the Publication audience row no longer carries the registry id its "
        f"findings must report under: {row!r}"
    )


def test_pr_description_sync_dimension_grades_the_audience_rule(
    capabilities_dir: Path,
) -> None:
    text = (capabilities_dir / "pr-description" / "capability.md").read_text(
        encoding="utf-8"
    )
    section = text.split("### S2b", 1)
    assert len(section) == 2, "pr-description lost its S2b self-containment section"
    body = section[1].split("\n### ", 1)[0]
    for needle in ("../../references/publication-audience.md", "private-context-ref"):
        assert needle in body, (
            f"S2b no longer names {needle!r} — the section grades the dimension, "
            "so a mention anywhere else in the file is not the same claim"
        )


@pytest.mark.parametrize("cap_name", BOT_GUARD_CAPABILITIES)
def test_bot_guard_capabilities_reach_bot_signatures(
    cap_name: str, capabilities_dir: Path
) -> None:
    text = (capabilities_dir / cap_name / "capability.md").read_text(encoding="utf-8")
    assert (
        "../../references/bot-signatures.md" in text
        or "../../references/pr-input-guards.md" in text
    ), (
        f"{cap_name} needs the bot-author catalog but links neither "
        "../../references/bot-signatures.md nor the standard "
        "../../references/pr-input-guards.md sequence that carries it"
    )


@pytest.mark.parametrize("cap_name", FLAGGED_OPERATION_PROPOSERS)
def test_flagged_operation_proposers_reach_harness_safety_nets(
    cap_name: str, capabilities_dir: Path
) -> None:
    text = (capabilities_dir / cap_name / "capability.md").read_text(encoding="utf-8")
    assert (
        "../../references/harness-safety-nets.md" in text
        or "../../references/force-push-impact.md" in text
    ), (
        f"{cap_name} proposes classifier-flagged operations but links neither "
        "../../references/harness-safety-nets.md nor "
        "../../references/force-push-impact.md, which carries its phrasing rules"
    )


def test_every_capability_is_classified(capabilities_dir: Path) -> None:
    """Safety wiring is a checklist: a new capability must be placed in the
    safety classes that fit it (or explicitly among the unclassified-safe)
    before it lands, and a deleted capability must leave every list.
    Membership in the non-safety lists (FORGE_SIDE, FORCE_PUSH) deliberately
    does NOT count as classified — being forge-side says nothing about
    whether the capability's safety classes were considered."""
    safety_classes = set(
        INGESTION_CAPABILITIES
        + SECRET_SCAN_CAPABILITIES
        + PUBLICATION_AUDIENCE_CAPABILITIES
        + BOT_GUARD_CAPABILITIES
        + FLAGGED_OPERATION_PROPOSERS
    )
    safety_classified = safety_classes | set(UNCLASSIFIED_SAFE_CAPABILITIES)
    every_list = safety_classified | set(FORCE_PUSH_CONSUMERS) | set(
        FORGE_SIDE_CAPABILITIES
    )
    on_disk = {p.parent.name for p in capabilities_dir.glob("*/capability.md")}
    unclassified = on_disk - safety_classified
    stale = every_list - on_disk
    contradictory = safety_classes & set(UNCLASSIFIED_SAFE_CAPABILITIES)
    assert not unclassified, (
        "capabilities missing from the safety-wiring class lists in this "
        f"test (add each to the classes that fit it): {sorted(unclassified)}"
    )
    assert not stale, (
        f"class lists name capabilities that no longer exist: {sorted(stale)}"
    )
    assert not contradictory, (
        "capabilities listed both in a safety class and as unclassified-safe "
        f"(pick one): {sorted(contradictory)}"
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


def test_mixed_scope_repair_bypasses_the_curation_rule(references_dir: Path) -> None:
    """The documented repair silently did nothing on the common tree.

    `git reset --soft HEAD~` leaves the reverted commit staged, but any tracked
    edit still in the worktree — the usual state, since the smell is noticed
    while working — makes that pile read as hand-curated to SPLIT's curation
    rule, which forces it to one commit. The repair then rebuilds the same
    mixed-scope commit it was invoked to take apart.
    """
    text = (references_dir / "commit-smells.md").read_text(encoding="utf-8")
    entry = text.split("### `mixed-scope`", 1)[1].split("\n### ", 1)[0]
    # The invocation, not the flag: the sentence explaining why the flag is
    # needed also contains "--split", so a bare substring check stayed green
    # after the recipe itself lost it. Mutation found that.
    assert "/git-toolkit commit --split" in entry, (
        "the post-commit repair does not force series analysis, so the curation "
        "rule converts it into a no-op on any tree with unstaged work"
    )
    assert "curation rule" in entry, (
        "the entry does not say why the flag is required, so the next edit drops "
        "it as redundant"
    )
    assert "git update-ref -d HEAD" in entry, (
        "the repair has no root-commit path, where `HEAD~` does not resolve — the "
        "same initial-commit case the split protocol otherwise supports"
    )
