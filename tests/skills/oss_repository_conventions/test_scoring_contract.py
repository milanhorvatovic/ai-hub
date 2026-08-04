"""Enforce the scoring contract in `references/oss-health-rubric.md`.

Three invariants keep two independent auditors on the same number: every
`capability check-id` citation anywhere in the skill's markdown (baseline
roll-ups, worked report lines, NDJSON samples) resolves to a check the named
capability's Audit section defines — a definition bullet carries no
capability-name prefix, so declarations never register as citations;
conditional severities use the one codified notation
(`**base** (→ **resolved** when <condition>)`) so the resolved severity is
always derivable; and the worked score computation in
`references/worked-example.md` reproduces its stated number under the
rubric's rules — weight by resolved severity, only `pass` earns credit,
`warn` earns zero, `skip` excluded.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

# Same bullet shape test_capability_shape.py locks:
# `- `kebab-id` — **severity**` …
_CHECK_RE = re.compile(r"^- `([a-z][a-z0-9-]*)` — \*\*(must|should|could)\*\*")

_CONDITIONAL_RE = re.compile(r"\(→ \*\*(must|should|could)\*\* (?:when|for) [^)]+\)")

_WEIGHT = {"must": 3, "should": 2, "could": 1}


def _defined_checks(capabilities_dir: Path) -> dict[str, set[str]]:
    """Map capability name -> check ids its Audit section declares."""
    defined: dict[str, set[str]] = {}
    for cap in sorted(capabilities_dir.glob("*/capability.md")):
        defined[cap.parent.name] = {
            m.group(1)
            for line in cap.read_text(encoding="utf-8").splitlines()
            if (m := _CHECK_RE.match(line))
        }
    return defined


def test_cited_check_ids_are_defined(
    skill_root: Path, capabilities_dir: Path
) -> None:
    """A citation naming a capability and a check — `capability `check-id``
    prose (the baseline roll-up style), `(capability: check-id` report lines,
    or `"domain":"…","check":"…"` NDJSON samples — must point at a check the
    named capability's Audit section defines."""
    defined = _defined_checks(capabilities_dir)
    cap_alt = "|".join(re.escape(name) for name in defined)
    citation_patterns = (
        re.compile(rf"\b({cap_alt})(?:'s)? `([a-z][a-z0-9-]*)`"),
        re.compile(rf"\(({cap_alt}): ([a-z][a-z0-9-]*)"),
        re.compile(rf'"domain":\s*"({cap_alt})",\s*"check":\s*"([a-z0-9-]+)"'),
    )
    problems: list[str] = []
    total = 0
    for md in sorted(skill_root.rglob("*.md")):
        if md.name == "CHANGELOG.md":  # release history, not contract text
            continue
        text = md.read_text(encoding="utf-8")
        for pattern in citation_patterns:
            for m in pattern.finditer(text):
                cap, check = m.group(1), m.group(2)
                total += 1
                if check not in defined[cap]:
                    problems.append(
                        f"{md.relative_to(skill_root)}: cites {cap} `{check}`"
                        " but that capability defines no such check"
                    )
    assert total > 0, "no check citations found — citation patterns broken?"
    assert not problems, "citations of undefined checks:\n" + "\n".join(problems)


def test_fixture_findings_cite_defined_checks(
    references_dir: Path, capabilities_dir: Path
) -> None:
    """Every finding in the NDJSON fixture names a defined domain/check pair."""
    defined = _defined_checks(capabilities_dir)
    lines = (references_dir / "output-format.example.ndjson").read_text(
        encoding="utf-8"
    )
    problems: list[str] = []
    for i, line in enumerate(filter(str.strip, lines.splitlines()), start=1):
        obj = json.loads(line)
        if obj["check"] not in defined.get(obj["domain"], set()):
            problems.append(f"line {i}: {obj['domain']}: `{obj['check']}` undefined")
    assert not problems, "fixture cites undefined checks:\n" + "\n".join(problems)


def test_conditional_severities_use_codified_notation(
    capabilities_dir: Path,
) -> None:
    """Every `(→ …)` in a capability body sits in a check bullet's severity
    slot, matches `(→ **severity** when|for <condition>)`, and resolves to a
    severity different from the base (a self-resolving conditional is noise)."""
    problems: list[str] = []
    found = 0
    for cap in sorted(capabilities_dir.glob("*/capability.md")):
        for line in cap.read_text(encoding="utf-8").splitlines():
            if "(→" not in line:
                continue
            m = _CHECK_RE.match(line)
            if m is None:
                problems.append(
                    f"{cap.parent.name}: '(→' outside a check bullet: {line[:70]}"
                )
                continue
            found += 1
            check_id, base = m.group(1), m.group(2)
            if not line[m.end() :].startswith(" (→"):
                problems.append(
                    f"{cap.parent.name}: {check_id}: conditional must follow"
                    " the base severity directly"
                )
            cm = _CONDITIONAL_RE.search(line)
            if cm is None:
                problems.append(
                    f"{cap.parent.name}: {check_id}: conditional doesn't match"
                    " `(→ **severity** when|for <condition>)`"
                )
            elif cm.group(1) == base:
                problems.append(
                    f"{cap.parent.name}: {check_id}: resolves to its own base"
                    f" severity ({base})"
                )
    assert found > 0, "no conditional severities found — notation regex broken?"
    assert not problems, "conditional-severity problems:\n" + "\n".join(problems)


_ROW_RE = re.compile(
    r"^\| `([a-z][a-z0-9-]*)` \| ([a-z]+)[^|]*\| (\d+) \| (pass|warn|fail) \| (\d+) \|$"
)
_SCORE_RE = re.compile(
    r"score = \(([^)]*)\) / \(([^)]*)\) = (\d+) / (\d+) = (\d+)%"
)


def test_worked_score_computation_adds_up(
    references_dir: Path, capabilities_dir: Path
) -> None:
    """The worked example's hand computation follows the rubric: weights match
    the resolved severities, only `pass` earns, `warn` earns zero, and the
    stated score is the actual quotient — echoed by the report's domain line."""
    text = (references_dir / "worked-example.md").read_text(encoding="utf-8")
    section = text.split("### The score, computed", 1)
    assert len(section) == 2, "worked-example.md lost its score computation"
    body = section[1].split("\n## ", 1)[0]

    rows = [
        (m.group(1), m.group(2), int(m.group(3)), m.group(4), int(m.group(5)))
        for m in map(_ROW_RE.match, body.splitlines())
        if m
    ]
    assert rows, "no computation rows parsed"

    defined = _defined_checks(capabilities_dir)
    problems: list[str] = []
    for check_id, severity, weight, status, earns in rows:
        if check_id not in defined["ci-automation"]:
            problems.append(f"{check_id}: not a ci-automation check")
        if _WEIGHT.get(severity) != weight:
            problems.append(f"{check_id}: weight {weight} != {severity}'s weight")
        if earns != (weight if status == "pass" else 0):
            problems.append(
                f"{check_id}: {status} must earn "
                f"{weight if status == 'pass' else 0}, shows {earns}"
            )
    assert any(status == "warn" for _, _, _, status, _ in rows), (
        "the computation must include a warn row — it proves warn earns zero"
    )
    assert not problems, "computation rows off-contract:\n" + "\n".join(problems)

    score = _SCORE_RE.search(body)
    assert score, "score line doesn't match `score = (…) / (…) = N / D = P%`"
    earned_terms = [int(n) for n in re.findall(r"\d+", score.group(1))]
    weight_terms = [int(n) for n in re.findall(r"\d+", score.group(2))]
    numerator, denominator, percent = map(int, score.group(3, 4, 5))
    assert sum(earned_terms) == numerator == sum(e for *_, e in rows)
    assert sum(weight_terms) == denominator == sum(w for _, _, w, _, _ in rows)
    assert percent == round(100 * numerator / denominator)

    domain_line = re.search(r"· ci (\d+)%", text)
    assert domain_line, "report block lost its `ci NN%` domain score"
    assert int(domain_line.group(1)) == percent, (
        "report's ci domain score disagrees with the worked computation"
    )
