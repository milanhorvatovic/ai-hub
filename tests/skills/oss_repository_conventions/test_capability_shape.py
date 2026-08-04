"""Enforce the locked capability shape.

Every capability follows the same skeleton (Modes → … → Anti-patterns) and
declares its audit checks in one uniform bullet form
(`- \\`id\\` — **severity**. criterion. why`). These tests lock that shape so a
new or edited capability can't silently drift from the contract recorded in
`references/oss-health-rubric.md`. `## Languages` is intentionally optional —
language-agnostic domains (governance, security-policy, …) omit it.

The scaffold-template convention is part of the shape: every capability's
scaffold content lives in `references/scaffold-templates.md` as fenced blocks
(the structural suite's collectors treat fenced content as data, so
target-repo links inside a template are never mistaken for skill navigation),
with the H1 naming the capability and the file. The one exemption is raw
copyable artifacts, named `*.example.*` and never markdown.
"""

from __future__ import annotations

import re
from pathlib import Path

REQUIRED_SECTIONS = (
    "Modes",
    "Inputs & guards",
    "Scan",
    "Audit",
    "Scaffold",
    "Output",
    "Edge cases",
    "Anti-patterns",
)

# `- `kebab-id` — **severity**` … (tolerates trailing `(→ **x** …)` and `· scorecard: …`)
_CHECK_RE = re.compile(r"^- `([a-z][a-z0-9-]*)` — \*\*(must|should|could)\*\*")


def _sections(text: str) -> set[str]:
    return {m.group(1).strip() for m in re.finditer(r"^## (.+)$", text, re.MULTILINE)}


def _capabilities(capabilities_dir: Path) -> list[Path]:
    return sorted(capabilities_dir.glob("*/capability.md"))


def test_every_capability_has_required_sections(capabilities_dir: Path) -> None:
    bad: list[str] = []
    for cap in _capabilities(capabilities_dir):
        present = _sections(cap.read_text(encoding="utf-8"))
        missing = set(REQUIRED_SECTIONS) - present
        if missing:
            bad.append(f"{cap.parent.name}: missing {sorted(missing)}")
    assert not bad, "capabilities missing required sections:\n" + "\n".join(bad)


def test_scaffold_templates_present_and_titled(capabilities_dir: Path) -> None:
    """Every capability ships `references/scaffold-templates.md`, and its H1
    is `# <capability> — scaffold templates` — one predictable home per
    capability for scaffold content."""
    bad: list[str] = []
    for cap in _capabilities(capabilities_dir):
        templates = cap.parent / "references" / "scaffold-templates.md"
        if not templates.is_file():
            bad.append(f"{cap.parent.name}: missing references/scaffold-templates.md")
            continue
        lines = templates.read_text(encoding="utf-8").splitlines()
        if not lines:
            bad.append(f"{cap.parent.name}: references/scaffold-templates.md is empty")
            continue
        first_line = lines[0]
        expected = f"# {cap.parent.name} — scaffold templates"
        if first_line != expected:
            bad.append(f"{cap.parent.name}: H1 {first_line!r} != {expected!r}")
    assert not bad, "scaffold-template convention violations:\n" + "\n".join(bad)


def test_template_content_is_fenced(capabilities_dir: Path) -> None:
    """Template content is data, carried in fenced blocks — every
    scaffold-templates.md has at least one fence, and no capability ships a
    raw `*.template.*` file (whose live relative links would read as skill
    navigation)."""
    raw_templates = [
        str(f.relative_to(capabilities_dir))
        for f in sorted(capabilities_dir.glob("*/references/*"))
        if ".template." in f.name
    ]
    assert not raw_templates, f"raw template files: {raw_templates}"
    unfenced = [
        str(f.relative_to(capabilities_dir))
        for f in sorted(capabilities_dir.glob("*/references/scaffold-templates.md"))
        if not re.search(r"^\s{0,3}(?:`{3,}|~{3,})", f.read_text(encoding="utf-8"), re.MULTILINE)
    ]
    assert not unfenced, f"scaffold-templates.md without a fenced block: {unfenced}"


def test_raw_reference_files_carry_example_marker(capabilities_dir: Path) -> None:
    """The only non-markdown reference files are copyable raw artifacts named
    `*.example.*` (e.g. a JSON payload passed to a CLI as-is) — the documented
    exemption from the fenced-template convention. The marker and markdown are
    mutually exclusive: a `*.example.md` would claim the exemption while being
    the very thing the exemption exists to fence off."""
    unmarked = [
        str(f.relative_to(capabilities_dir))
        for f in sorted(capabilities_dir.glob("*/references/*"))
        if f.is_file() and f.suffix != ".md" and ".example." not in f.name
    ]
    assert not unmarked, f"raw reference files without the .example. marker: {unmarked}"
    markdown_marked = [
        str(f.relative_to(capabilities_dir))
        for f in sorted(capabilities_dir.glob("*/references/*.example.md"))
    ]
    assert not markdown_marked, f"markdown files claiming the raw-artifact marker: {markdown_marked}"


def test_audit_check_bullets_are_well_formed(capabilities_dir: Path) -> None:
    """Every audit-check bullet uses a kebab-case id and a canonical severity,
    and ids are unique within a capability (the rubric's check schema)."""
    problems: list[str] = []
    total = 0
    for cap in _capabilities(capabilities_dir):
        seen: set[str] = set()
        for raw in cap.read_text(encoding="utf-8").splitlines():
            if not raw.startswith("- `"):
                continue
            m = _CHECK_RE.match(raw)
            if not m:
                # A backtick bullet that isn't a check (e.g. a plain list item)
                # is fine; only lines shaped like a check must parse cleanly.
                if re.match(r"^- `[a-z][a-z0-9-]*` — \*\*", raw):
                    problems.append(f"{cap.parent.name}: malformed check: {raw}")
                continue
            check_id = m.group(1)
            total += 1
            if check_id in seen:
                problems.append(f"{cap.parent.name}: duplicate check id {check_id!r}")
            seen.add(check_id)
    assert total > 0, "no audit checks found across capabilities"
    assert not problems, "audit-check problems:\n" + "\n".join(problems)
