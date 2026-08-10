"""Structural contracts for the identities automation acts as.

The rule and the per-workflow audit live in `docs/adr/0002-automation-identity.md`.
These pin the things about it that go stale silently: a workflow gaining write access
without anyone re-reading the rule, a secret arriving that no row accounts for, and a
workflow arriving that the audit never covered.
"""

import re
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_WORKFLOW_DIR = _REPO_ROOT / ".github" / "workflows"
_ADR = _REPO_ROOT / "docs" / "adr" / "0002-automation-identity.md"

# The jobs the ADR's audit records as write-privileged, and why each earns it: opening
# the release PR, uploading release assets, uploading the catalog manifest.
_WRITE_PRIVILEGED_JOBS = {
    ("release-please.yml", "release-please"),
    ("release-please.yml", "bundle"),
    ("release-please.yml", "catalog-publish"),
}

# `contents` and `pull-requests` are the two scopes that let a workflow author an event
# — a push, a branch, a pull request — so they are the ones the identity rule turns on.
# `security-events`, `id-token`, and `attestations` write elsewhere and cascade nothing.
_EVENT_AUTHORING_SCOPES = ("contents", "pull-requests")


def _workflows() -> list[Path]:
    found = sorted(_WORKFLOW_DIR.glob("*.y*ml"))
    assert found, "no workflow files found"
    return found


def _block(lines: list[str], start: int, indent: int) -> list[str]:
    """The lines below `start` indented deeper than `indent`, stopping at the first that is not."""
    body = []
    for line in lines[start + 1 :]:
        if not line.strip():
            continue
        if len(line) - len(line.lstrip()) <= indent:
            break
        body.append(line)
    return body


def _value(text: str) -> str:
    """A YAML scalar's value: comment dropped, surrounding quotes stripped.

    `contents: "write"` grants exactly what `contents: write` grants, so a check that
    reads only the bare form would let the quoted one through — the open direction.
    """
    return text.split("#", 1)[0].strip().strip("\"'")


def _granted_write(block: list[str], inline: str = "") -> set[str]:
    """Event-authoring scopes granted `write` by one `permissions:` declaration.

    `write-all` is the shorthand that grants every scope at once, so it has to count as
    both — a guard that only reads `<scope>: write` would read a job holding full write
    access as holding none, which is the direction that fails open.
    """
    if _value(inline) == "write-all":
        return set(_EVENT_AUTHORING_SCOPES)

    granted = set()
    for line in block:
        if _value(line) == "write-all":
            return set(_EVENT_AUTHORING_SCOPES)
        match = re.match(r"\s*([a-z-]+):(.*)$", line)
        if match and match.group(1) in _EVENT_AUTHORING_SCOPES and _value(match.group(2)) == "write":
            granted.add(match.group(1))
    return granted


def _jobs(lines: list[str]) -> list[tuple[str, int]]:
    """Each top-level job as `(name, line index)`, scoped to the block under `jobs:`.

    Matching a two-space key anywhere in the file would collect the trigger names under
    `on:` as well — `push`, `pull_request`, `schedule` — which is how a count of them
    can look healthy while the real jobs are unreadable.
    """
    start = next((i for i, line in enumerate(lines) if line.rstrip() == "jobs:"), None)
    if start is None:
        return []

    found = []
    for index in range(start + 1, len(lines)):
        line = lines[index]
        if line.strip() and not line.startswith(" "):
            break
        match = re.match(r"^  ([A-Za-z0-9_-]+):$", line)
        if match:
            found.append((match.group(1), index))
    return found


def _audit_section(adr: str) -> str:
    """The ADR's per-workflow audit, alone — not the whole document.

    Asking whether the file mentions a workflow anywhere would pass on a name that
    appears only in the prose around the table, which is not what being audited means.
    """
    _, _, after = adr.partition("### What each workflow uses today")
    section, _, _ = after.partition("\n### ")
    assert section.strip(), "the ADR's audit section was not found under its heading"
    return section


def test_every_workflow_declares_a_read_only_floor() -> None:
    for workflow in _workflows():
        lines = workflow.read_text(encoding="utf-8").splitlines()
        tops = [i for i, line in enumerate(lines) if re.match(r"^permissions:", line)]
        assert len(tops) == 1, f"{workflow.name}: expected exactly one top-level permissions block"
        inline = lines[tops[0]].partition(":")[2]
        assert not _granted_write(_block(lines, tops[0], 0), inline), (
            f"{workflow.name}: the workflow-wide floor grants write; elevate per job instead"
        )


def test_only_the_release_jobs_can_author_events() -> None:
    # Derived from the tree rather than counted, so a new privileged job fails here and
    # sends its author to the rule — which is the whole point of writing the rule down.
    elevated = set()
    for workflow in _workflows():
        lines = workflow.read_text(encoding="utf-8").splitlines()
        jobs = _jobs(lines)

        # A workflow whose jobs this parser cannot see contributes nothing and would
        # leave the comparison below satisfied by the others — so an unreadable file has
        # to fail here rather than pass quietly. Two-space job indentation is the house
        # form, not a YAML requirement.
        assert jobs, f"{workflow.name}: no jobs parsed; the guard cannot see this file"

        for name, index in jobs:
            body = _block(lines, index, 2)
            for offset, inner in enumerate(body):
                if re.match(r"\s*permissions:", inner):
                    indent = len(inner) - len(inner.lstrip())
                    if _granted_write(_block(body, offset, indent), inner.partition(":")[2]):
                        elevated.add((workflow.name, name))

    assert elevated == _WRITE_PRIVILEGED_JOBS, (
        "a job's write access to contents or pull-requests changed; the identity it acts "
        "as is a decision, so read docs/adr/0002-automation-identity.md before updating "
        f"this set (added: {sorted(elevated - _WRITE_PRIVILEGED_JOBS)}, "
        f"removed: {sorted(_WRITE_PRIVILEGED_JOBS - elevated)})"
    )


def test_every_secret_a_workflow_uses_is_named_in_the_audit() -> None:
    # A new secret is a new identity, which is the thing the ADR exists to decide. The
    # audit table records the identity each workflow acts as, so a secret reaching a
    # workflow without reaching that table means an identity nobody chose.
    audit = _audit_section(_ADR.read_text(encoding="utf-8"))
    used = set()
    for workflow in _workflows():
        used |= set(re.findall(r"secrets\.([A-Z_][A-Z0-9_]*)", workflow.read_text(encoding="utf-8")))
    assert used, "no secrets referenced by any workflow; the pattern probably stopped matching"

    unrecorded = sorted(name for name in used if name not in audit)
    assert not unrecorded, (
        f"secrets used by a workflow but absent from the ADR's audit: {', '.join(unrecorded)}"
    )


def test_the_audit_covers_every_workflow() -> None:
    # An audit is only as good as its coverage, and a new workflow is exactly what it
    # would miss. Each is named by its stem, in backticks, inside the audit itself.
    audit = _audit_section(_ADR.read_text(encoding="utf-8"))
    missing = [w.name for w in _workflows() if f"`{w.stem}`" not in audit]

    assert not missing, (
        f"workflows absent from the ADR's audit: {', '.join(missing)} — add a row to "
        "'What each workflow uses today' in docs/adr/0002-automation-identity.md"
    )
