"""Cross-reference and JSON Schema tests for git-toolkit references/.

Two concerns:

1. **Link resolution.** Capabilities link to reference files via relative
   paths like `../../references/<name>.md`. If a capability points at a
   missing reference, the load will silently degrade. This test catches the
   broken link at change time.

2. **JSON Schema validity.** The review-output NDJSON schema is shipped as
   `references/review-output.schema.json`. It must parse as valid JSON and
   declare a $schema URI that names a recognized Draft.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest


def _collect_relative_links(md_path: Path) -> list[tuple[str, int]]:
    """Return (relative-link, 1-based-line-number) for every backtick-quoted
    relative `.md`/`.json` path into the skill tree.

    Matches skill-internal relative links ending in `.md` or `.json`, in
    either form: a `../`-prefixed traversal (so intra-capability sibling
    links like `../pr-conversation-resolve/capability.md` are validated
    alongside `../../references/foo.md`, and reference links to non-`.md`
    artifacts like `../../references/review-output.schema.json` are not
    silently skipped), or a `references/` / `capabilities/` prefix (as used
    from SKILL.md). Repo-root path mentions like
    `.github/copilot-instructions.md` and bare prose mentions like
    `format-conventions.md` are intentionally excluded — they are not
    skill-relative links.
    """
    text = md_path.read_text(encoding="utf-8")
    out: list[tuple[str, int]] = []
    for lineno, line in enumerate(text.splitlines(), start=1):
        for m in re.finditer(
            r"`((?:(?:\.\./)+[A-Za-z0-9_./-]+"
            r"|(?:references|capabilities)/[A-Za-z0-9_./-]+)\.(?:md|json))`",
            line,
        ):
            out.append((m.group(1), lineno))
    return out


def test_capability_links_resolve(
    skill_root: Path, capabilities_dir: Path
) -> None:
    """Every relative path linked from a capability.md must resolve, and must
    stay within the skill tree (a link that escapes skill_root, e.g.
    `../../../../README.md`, is treated as broken even if the target exists)."""
    skill_root_resolved = skill_root.resolve()
    broken: list[str] = []
    for cap_dir in sorted(capabilities_dir.iterdir()):
        cap_md = cap_dir / "capability.md"
        if not cap_md.is_file():
            continue
        for link, lineno in _collect_relative_links(cap_md):
            target = (cap_md.parent / link).resolve()
            if not target.is_file():
                broken.append(f"{cap_md.relative_to(skill_root)}:{lineno} -> {link} (missing)")
            elif not target.is_relative_to(skill_root_resolved):
                broken.append(f"{cap_md.relative_to(skill_root)}:{lineno} -> {link} (escapes skill tree)")
    assert not broken, "broken relative links in capabilities:\n" + "\n".join(broken)


def test_skill_md_reference_links_resolve(
    skill_md: Path, references_dir: Path
) -> None:
    """Every `references/<name>` link in SKILL.md must exist — including
    non-`.md` artifacts like the JSON Schema and the NDJSON example fixture,
    so a renamed schema/example doesn't silently break the router's list."""
    text = skill_md.read_text(encoding="utf-8")
    referenced = re.findall(
        r"references/([A-Za-z0-9_./-]+\.(?:md|json|ndjson))", text
    )
    missing = [r for r in referenced if not (references_dir / r).is_file()]
    assert not missing, f"SKILL.md references missing files: {missing}"


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
