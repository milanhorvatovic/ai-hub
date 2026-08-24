"""Rule-id registry and REVIEW output-contract tests for git-toolkit.

`references/review-output.md` declares a single rule-id registry — the
commit-smells.md catalog plus its own check/meta table — and
`references/review-output.schema.json` enforces membership through the `rule`
enum. These tests hold every listing of the vocabulary in sync: catalog
headings, registry table, schema enum, the example fixture, the NDJSON
examples embedded in prose, and the rule ids that capability Rule-catalog
sections cite. They also pin the deduplication: the retired spellings
(`past-tense-verb`, `overlong-subject`) may survive only in the registry's
deprecation note, and commit-message REVIEW no longer documents the
pre-contract `ok`/`warn`/`fixme` per-commit table.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

_RULE_ID = re.compile(r"^[a-z][a-z0-9]*(-[a-z0-9]+)*$")
_DEPRECATED_IDS = ("past-tense-verb", "overlong-subject")


def _catalog_ids(references_dir: Path) -> list[str]:
    """Every smell id declared as a `### `<id>`` heading in commit-smells.md."""
    text = (references_dir / "commit-smells.md").read_text(encoding="utf-8")
    return re.findall(r"^### `([a-z0-9-]+)`", text, flags=re.MULTILINE)


def _registry_table_ids(references_dir: Path) -> list[str]:
    """Check/meta ids from the registry table in review-output.md."""
    text = (references_dir / "review-output.md").read_text(encoding="utf-8")
    assert "## Rule-id registry" in text, (
        "review-output.md lost its Rule-id registry section"
    )
    section = text.split("## Rule-id registry", 1)[1].split("\n## ", 1)[0]
    return re.findall(r"^\| `([a-z0-9-]+)` \|", section, flags=re.MULTILINE)


def _schema(references_dir: Path) -> dict:
    return json.loads(
        (references_dir / "review-output.schema.json").read_text(encoding="utf-8")
    )


def test_catalog_ids_are_wellformed_unique_and_counted(references_dir: Path) -> None:
    """Catalog headings are the smell half of the registry; the Rule
    selectivity example's "N registry rules" figure must match the real
    registry size (catalog headings + check/meta table)."""
    ids = _catalog_ids(references_dir)
    assert ids, "no `### `<id>`` headings found in commit-smells.md"
    malformed = [i for i in ids if not _RULE_ID.fullmatch(i)]
    assert not malformed, f"catalog ids not kebab-case: {malformed}"
    assert len(ids) == len(set(ids)), "duplicate catalog headings"
    text = (references_dir / "commit-smells.md").read_text(encoding="utf-8")
    claimed = {int(n) for n in re.findall(r"of (\d+) registry rules", text)}
    total = len(ids) + len(_registry_table_ids(references_dir))
    claimed_display = ", ".join(map(str, sorted(claimed))) or "nothing"
    assert claimed == {total}, (
        f"commit-smells.md's Rule selectivity example claims "
        f"{claimed_display} registry rules but the registry holds {total}"
    )


def test_registry_prose_counts_the_catalog_it_points_at(references_dir: Path) -> None:
    """review-output.md's "(N rules)" figure for the catalog half must be real.

    Its sibling figure in commit-smells.md has been asserted since the registry
    landed; this one was written the same day and guarded by nothing, so adding
    a smell left it silently stale — a registry describing its own size wrongly,
    in the file that defines what the registry is.
    """
    text = (references_dir / "review-output.md").read_text(encoding="utf-8")
    section = text.split("## Rule-id registry", 1)[1].split("\n## ", 1)[0]
    claimed = [int(n) for n in re.findall(r"\((\d+) rules\)", section)]
    assert len(claimed) == 1, (
        f"expected exactly one '(N rules)' figure in the registry section, found {claimed}"
    )
    actual = len(_catalog_ids(references_dir))
    assert claimed[0] == actual, (
        f"registry section claims the catalog holds {claimed[0]} rules; it holds {actual}"
    )


def test_registry_table_extends_the_catalog_without_overlap(
    references_dir: Path,
) -> None:
    table = _registry_table_ids(references_dir)
    assert table, "registry table in review-output.md declares no ids"
    malformed = [i for i in table if not _RULE_ID.fullmatch(i)]
    assert not malformed, f"registry-table ids not kebab-case: {malformed}"
    assert len(table) == len(set(table)), "duplicate registry-table ids"
    overlap = set(table) & set(_catalog_ids(references_dir))
    assert not overlap, (
        f"ids defined in both commit-smells.md and the registry table: {overlap}"
    )


def test_schema_enum_is_exactly_the_registry(references_dir: Path) -> None:
    """The `rule` enum is the registry's machine form: catalog headings plus
    the registry table, nothing else, no duplicates, every entry kebab-case
    per the schema's own pattern."""
    schema = _schema(references_dir)
    rule_spec = schema["properties"]["rule"]
    assert "enum" in rule_spec, "schema rule property lost its registry enum"
    enum = rule_spec["enum"]
    assert len(enum) == len(set(enum)), "duplicate ids in schema enum"
    pattern = rule_spec["pattern"]
    off_pattern = [i for i in enum if not re.fullmatch(pattern, i)]
    assert not off_pattern, f"enum ids fail the schema's own pattern: {off_pattern}"
    registry = set(_catalog_ids(references_dir)) | set(
        _registry_table_ids(references_dir)
    )
    assert set(enum) == registry, (
        "schema enum and prose registry diverge — "
        f"enum-only: {sorted(set(enum) - registry)}, "
        f"registry-only: {sorted(registry - set(enum))}"
    )


def test_fixture_ids_resolve_to_the_registry(references_dir: Path) -> None:
    enum = set(_schema(references_dir)["properties"]["rule"]["enum"])
    lines = [
        ln
        for ln in (references_dir / "review-output.example.ndjson")
        .read_text(encoding="utf-8")
        .splitlines()
        if ln.strip()
    ]
    unregistered = {
        json.loads(ln)["rule"] for ln in lines
    } - enum
    assert not unregistered, (
        f"fixture uses ids outside the registry enum: {sorted(unregistered)}"
    )


def test_fixture_verdict_tallies_the_findings_it_closes(
    references_dir: Path,
) -> None:
    """The verdict's excerpt tallies rule results, and the failing ones are
    all visible by contract: a FAIL or MOSTLY-PASS rule emits one object per
    offending target, while aggregate PASS objects may be elided. So those two
    counts are checkable against the stream and were both wrong — a summary
    line that miscounts the findings above it teaches the shape wrongly to
    every consumer reading the fixture to learn it."""
    lines = [
        json.loads(ln)
        for ln in (references_dir / "review-output.example.ndjson")
        .read_text(encoding="utf-8")
        .splitlines()
        if ln.strip()
    ]
    verdict = [obj for obj in lines if obj["rule"] == "verdict"]
    assert len(verdict) == 1, "the stream must close with exactly one verdict"
    excerpt = verdict[0]["details"]["excerpt"]
    for result in ("FAIL", "MOSTLY-PASS"):
        claimed = re.search(rf"(\d+) {re.escape(result)}\b", excerpt)
        assert claimed, f"verdict excerpt does not tally {result}: {excerpt!r}"
        actual = sum(
            1 for obj in lines if obj["rule"] != "verdict" and obj["result"] == result
        )
        assert int(claimed.group(1)) == actual, (
            f"verdict claims {claimed.group(1)} {result} findings; the stream "
            f"carries {actual}"
        )


def _jsonl_blocks(text: str) -> list[str]:
    return re.findall(r"```jsonl\r?\n(.*?)```", text, flags=re.DOTALL)


def test_embedded_ndjson_examples_validate_against_the_contract(
    references_dir: Path, capabilities_dir: Path
) -> None:
    """Every ```jsonl example in review-output.md and the capability docs —
    including commit-message REVIEW's documented output — must satisfy the
    schema's core invariants and the registry enum."""
    schema = _schema(references_dir)
    enum = set(schema["properties"]["rule"]["enum"])
    result_enum = set(schema["properties"]["result"]["enum"])
    scope_enum = set(schema["properties"]["scope"]["enum"])
    sources = [references_dir / "review-output.md"] + sorted(
        capabilities_dir.glob("*/capability.md")
    )
    problems: list[str] = []
    seen_blocks = 0
    for path in sources:
        for block in _jsonl_blocks(path.read_text(encoding="utf-8")):
            seen_blocks += 1
            for i, line in enumerate(
                (ln for ln in block.splitlines() if ln.strip()), start=1
            ):
                where = f"{path.parent.name}/{path.name} block line {i}"
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError as exc:
                    problems.append(f"{where}: invalid JSON ({exc})")
                    continue
                if obj.get("rule") not in enum:
                    problems.append(f"{where}: rule {obj.get('rule')!r} unregistered")
                if obj.get("result") not in result_enum:
                    problems.append(f"{where}: result {obj.get('result')!r} not in enum")
                if obj.get("scope") not in scope_enum:
                    problems.append(f"{where}: scope {obj.get('scope')!r} not in enum")
                if obj.get("scope") == "commit" and "sha" not in obj:
                    problems.append(f"{where}: scope=commit requires sha")
                if obj.get("scope") in {"branch", "range", "pr"} and "ref" not in obj:
                    problems.append(f"{where}: scope={obj.get('scope')} requires ref")
                if obj.get("result") in {"FAIL", "MOSTLY-PASS"} and "fix" not in obj:
                    problems.append(f"{where}: result={obj['result']} requires fix")
    assert seen_blocks >= 2, (
        "expected jsonl examples in review-output.md and commit-message "
        f"(found {seen_blocks} blocks)"
    )
    assert not problems, "embedded NDJSON examples break the contract:\n" + "\n".join(
        problems
    )


def _rule_catalog_sections(capabilities_dir: Path) -> list[tuple[str, str]]:
    # A Step-0 heading is only a rule-vocabulary section when it names the
    # vocabulary — "Rule catalog" / "Rule selectivity". Keying on the number
    # alone was safe until commit-message added a "### 0. Pre-flight" section;
    # that one declares no rule ids, so its inlined shell recipe
    # (`git log … | head …`) must not be swept as if it cited them. Requiring
    # "Rule" in the heading keeps the sweep on the sections it means to check.
    sections: list[tuple[str, str]] = []
    for cap in sorted(capabilities_dir.glob("*/capability.md")):
        text = cap.read_text(encoding="utf-8")
        for m in re.finditer(
            r"^### 0[^\n]*[Rr]ule[^\n]*$(.*?)(?=^#{2,3} |\Z)",
            text,
            flags=re.MULTILINE | re.DOTALL,
        ):
            sections.append((cap.parent.name, m.group(1)))
    return sections


# Non-rule words the Step-0 sections legitimately backtick. Deliberate
# allowlist, same philosophy as the safety-class lists in test_references:
# a new single-word token fails the sweep until it is either registered as
# a rule id or consciously listed here, so single-word ids (e.g. `verdict`)
# cannot slip past unvalidated.
_STEP0_PROSE_WORDS = {"rule", "details"}


def test_capability_rule_catalog_sections_resolve_to_the_registry(
    references_dir: Path, capabilities_dir: Path
) -> None:
    """Every kebab-case rule id cited in a capability's Step 0 / Step 0b
    rule-vocabulary sections must be a registry member — the "every id in
    capability text resolves to the registry" criterion, applied to the
    sections that declare rule vocabulary."""
    enum = set(_schema(references_dir)["properties"]["rule"]["enum"])
    sections = _rule_catalog_sections(capabilities_dir)
    assert sections, "no Step-0 rule-vocabulary sections found"
    offenders: list[str] = []
    for cap_name, section in sections:
        for span in re.findall(r"`([^`]+)`", section):
            span = re.sub(r"^rules:\s*", "", span)
            for token in re.split(r"[,\s]+", span):
                if not token or "." in token or "/" in token:
                    continue
                if not _RULE_ID.fullmatch(token):
                    continue
                if token in _STEP0_PROSE_WORDS:
                    continue
                if token not in enum:
                    offenders.append(f"{cap_name}: {token!r}")
    assert not offenders, (
        "capability rule-catalog sections cite unregistered ids:\n"
        + "\n".join(offenders)
    )


def _rule_id_table_cells(text: str) -> list[str]:
    """Backticked ids from any markdown table column headed `Rule id`."""
    cells: list[str] = []
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if not line.lstrip().startswith("|") or "Rule id" not in line:
            continue
        header = [c.strip() for c in line.strip().strip("|").split("|")]
        if "Rule id" not in header:
            continue
        col = header.index("Rule id")
        for row in lines[i + 1 :]:
            if not row.lstrip().startswith("|"):
                break
            parts = [c.strip() for c in row.strip().strip("|").split("|")]
            if col < len(parts):
                m = re.fullmatch(r"`([^`]+)`", parts[col])
                if m:
                    cells.append(m.group(1))
    return cells


def test_rule_id_table_columns_resolve_to_the_registry(
    references_dir: Path, capabilities_dir: Path
) -> None:
    """Capability check tables declare their vocabulary in a `Rule id` column
    (commit-message REVIEW Step 2); every cited id must be a registry
    member."""
    enum = set(_schema(references_dir)["properties"]["rule"]["enum"])
    offenders: list[str] = []
    found = 0
    for cap in sorted(capabilities_dir.glob("*/capability.md")):
        ids = _rule_id_table_cells(cap.read_text(encoding="utf-8"))
        found += len(ids)
        offenders += [
            f"{cap.parent.name}: {i!r}" for i in ids if i not in enum
        ]
    assert found, "no `Rule id` table columns found in any capability"
    assert not offenders, (
        "`Rule id` table columns cite unregistered ids:\n" + "\n".join(offenders)
    )


def test_review_result_tables_use_contract_results(
    skill_root: Path, references_dir: Path
) -> None:
    """Every `Rule | Result | Details` table in the tree — the contract's own
    template, capability output examples, the worked example — grades with the
    contract's result vocabulary only (no `ok`/`warn`/`none` dialects)."""
    result_enum = set(_schema(references_dir)["properties"]["result"]["enum"])
    offenders: list[str] = []
    tables = 0
    for path in sorted(skill_root.rglob("*.md")):
        lines = path.read_text(encoding="utf-8").splitlines()
        for i, line in enumerate(lines):
            header = [c.strip() for c in line.strip().strip("|").split("|")]
            if header != ["Rule", "Result", "Details"]:
                continue
            tables += 1
            for row in lines[i + 2 :]:  # skip the separator row
                if not row.lstrip().startswith("|"):
                    break
                parts = [c.strip() for c in row.strip().strip("|").split("|")]
                if len(parts) < 2:
                    continue
                for value in parts[1].split(" / "):
                    value = value.strip()
                    if value and value not in result_enum:
                        offenders.append(
                            f"{path.relative_to(skill_root)}: "
                            f"Result {value!r} in row {parts[0]!r}"
                        )
    assert tables >= 3, f"expected the contract/example Result tables, found {tables}"
    assert not offenders, (
        "Result tables use values outside the contract enum:\n"
        + "\n".join(offenders)
    )


def test_deprecated_spellings_survive_only_in_the_deprecation_note(
    skill_root: Path,
) -> None:
    """`past-tense-verb` and `overlong-subject` were unified into
    `imperative-mood` and `subject-length`; the old spellings may appear only
    on review-output.md's deprecation-note line, so no id exists in two
    spellings anywhere in the skill tree."""
    offenders: list[str] = []
    for path in sorted(skill_root.rglob("*")):
        if path.suffix not in {".md", ".json", ".ndjson"}:
            continue
        for lineno, line in enumerate(
            path.read_text(encoding="utf-8").splitlines(), start=1
        ):
            for dep in _DEPRECATED_IDS:
                if dep not in line:
                    continue
                allowed = (
                    path.name == "review-output.md" and "Deprecated" in line
                )
                if not allowed:
                    offenders.append(
                        f"{path.relative_to(skill_root)}:{lineno} uses {dep!r}"
                    )
    assert not offenders, (
        "deprecated rule-id spellings outside the deprecation note:\n"
        + "\n".join(offenders)
    )


def test_commit_message_review_dropped_the_per_commit_grading(
    capabilities_dir: Path,
) -> None:
    """The pre-contract REVIEW output — a per-commit `SHA | Subject | Status |
    Issues` table graded `ok`/`warn`/`fixme` — was unmappable to the
    PASS/MOSTLY-PASS/FAIL/N/A contract and must not resurface."""
    text = (capabilities_dir / "commit-message" / "capability.md").read_text(
        encoding="utf-8"
    )
    assert "| SHA | Subject | Status | Issues |" not in text, (
        "commit-message REVIEW reintroduced the per-commit status table"
    )
    assert "fixme" not in text.lower(), (
        "commit-message still uses the retired `fixme` grade"
    )
    assert "../../references/review-output.md" in text, (
        "commit-message REVIEW no longer cites the output contract"
    )
