"""Structural contracts for the identities automation acts as.

The rule and the per-workflow audit live in `docs/adr/0002-automation-identity.md`.
These pin the things about it that go stale silently: a job gaining default-token write
access without anyone re-reading the rule, a secret-backed identity arriving that no
audit row accounts for, and a workflow arriving that the audit never covered. The two
identity checks are complements — a `permissions:` block governs only the default token,
so it can never be the whole answer to which jobs act as something.
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

# Scopes whose `write` cannot produce an event another workflow could have been
# triggered by. Everything else counts, because the rule turns on whether a token can
# author something — `issues: write` creates issues and comments, `pages` and
# `deployments` create deployment events, and all of them are suppressed the same way.
# Stated as an exemption rather than an allowlist so a scope nobody has thought about
# counts by default: the list to maintain is the harmless one, and forgetting to extend
# it makes the guard noisy rather than blind.
_NON_AUTHORING_SCOPES = frozenset({"security-events", "id-token", "attestations"})


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


def _key(text: str) -> str:
    """A YAML mapping key, unquoted.

    Every identifier in this file's grammar may legally be quoted — the job id, the
    `permissions` key, and each scope inside it — and each spelling read only in its
    bare form is a grant this guard cannot see. Normalizing once, here, is what stops
    that from being a list of spellings someone has to keep extending.
    """
    return text.strip().strip("\"'")


_ALL_AUTHORING = frozenset({"*"})


def _granted_write(block: list[str], inline: str = "") -> frozenset[str]:
    """Event-authoring scopes granted `write` by one `permissions:` declaration.

    Every form GitHub accepts has to be read, because each unread one is a job holding
    write access that this guard reports as holding none: `write-all` grants everything
    at once, values may be quoted, and the whole mapping may be written inline in flow
    style. A form that is none of those is not assumed harmless — it returns a grant, so
    an unparsed declaration fails loudly instead of silently.
    """
    scalar = _value(inline)
    if scalar:
        if scalar == "write-all":
            return frozenset(_ALL_AUTHORING)
        if scalar in {"read-all", "{}"}:
            return frozenset()
        if scalar.startswith("{") and scalar.endswith("}"):
            return _flow_grants(scalar)
        return frozenset(_ALL_AUTHORING)  # unrecognized: fail closed

    granted = set()
    for line in block:
        if line.lstrip().startswith("#"):
            continue
        if _value(line) == "write-all":
            return frozenset(_ALL_AUTHORING)
        key, sep, value = line.partition(":")
        if not sep:
            return frozenset(_ALL_AUTHORING)  # unparsed entry: fail closed
        if _value(value) == "write" and _key(key) not in _NON_AUTHORING_SCOPES:
            granted.add(_key(key))
    return frozenset(granted)


def _flow_grants(scalar: str) -> frozenset[str]:
    """Event-authoring scopes granted `write` by an inline `{a: b, c: d}` mapping."""
    granted = set()
    for entry in scalar[1:-1].split(","):
        key, _, value = entry.partition(":")
        if _value(value) == "write" and _key(key) not in _NON_AUTHORING_SCOPES:
            granted.add(_key(key))
    return frozenset(granted)


def _jobs(lines: list[str]) -> list[tuple[str, int]]:
    """Each top-level job as `(name, line index)`, scoped to the block under `jobs:`.

    Matching a two-space key anywhere in the file would collect the trigger names under
    `on:` as well — `push`, `pull_request`, `schedule` — which is how a count of them
    can look healthy while the real jobs are unreadable.
    """
    start = next((i for i, line in enumerate(lines) if line.rstrip() == "jobs:"), None)
    if start is None:
        return []

    found, unparsed = [], []
    for index in range(start + 1, len(lines)):
        line = lines[index]
        if line.strip() and not line.startswith(" "):
            break
        if not re.match(r"^  \S", line) or line.lstrip().startswith("#"):
            continue
        key, sep, rest = line.partition(":")
        if sep and not _value(rest):
            found.append((_key(key), index))
        else:
            unparsed.append(line.strip())
    assert not unparsed, f"unreadable job declarations under `jobs:`: {unparsed}"
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


def _audit_rows_for(audit: str, stem: str) -> str:
    """The audit rows naming `stem`, joined — the rows that speak for one workflow.

    Scoping to the section is not enough on its own: asking whether a secret appears
    anywhere in the audit passes when some other workflow's row happens to name it, so
    two independently true facts stand in for the pairing nobody checked.
    """
    rows = [row for row in audit.splitlines() if row.startswith("|") and f"`{stem}`" in row]
    return "\n".join(rows)


def test_every_workflow_declares_a_read_only_floor() -> None:
    for workflow in _workflows():
        lines = workflow.read_text(encoding="utf-8").splitlines()
        tops = [
            i
            for i, line in enumerate(lines)
            if line[:1].strip() and _key(line.partition(":")[0]) == "permissions"
        ]
        assert len(tops) == 1, f"{workflow.name}: expected exactly one top-level permissions block"
        inline = lines[tops[0]].partition(":")[2]
        assert not _granted_write(_block(lines, tops[0], 0), inline), (
            f"{workflow.name}: the workflow-wide floor grants write; elevate per job instead"
        )


def test_only_the_release_jobs_elevate_the_default_token() -> None:
    # Named for what it reads. A `permissions:` block governs the default token and
    # nothing else, so this cannot be the check for "which jobs may author events" —
    # both Dependabot workflows author reviews, auto-merge state, and a synchronize
    # event through a secret-backed identity, and no permissions block mentions it.
    # That half belongs to the secret guard below, which pairs every secret a workflow
    # reads with the audit row naming it. Derived from the tree rather than counted, so
    # a newly elevated job fails here and sends its author to the rule.
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
                if _key(inner.partition(":")[0]) == "permissions":
                    indent = len(inner) - len(inner.lstrip())
                    if _granted_write(_block(body, offset, indent), inner.partition(":")[2]):
                        elevated.add((workflow.name, name))

    assert elevated == _WRITE_PRIVILEGED_JOBS, (
        "a job's default-token write access changed; the identity it acts "
        "as is a decision, so read docs/adr/0002-automation-identity.md before updating "
        f"this set (added: {sorted(elevated - _WRITE_PRIVILEGED_JOBS)}, "
        f"removed: {sorted(_WRITE_PRIVILEGED_JOBS - elevated)})"
    )


def test_every_secret_a_workflow_uses_is_named_in_its_own_audit_row() -> None:
    # A new secret is a new identity, which is the thing the ADR exists to decide — and
    # the row is the unit, not the table: a secret named somewhere in the audit says
    # nothing about the workflow now reading it, so each is checked against the rows
    # that speak for it. Both expression forms count, since `secrets.X` and
    # `secrets['X']` reach the same value and only one of them used to be read here.
    audit = _audit_section(_ADR.read_text(encoding="utf-8"))
    pattern = re.compile(r"""secrets(?:\.([A-Za-z_]\w*)|\[\s*['"]([A-Za-z_]\w*)['"]\s*\])""")

    total, unrecorded = 0, []
    for workflow in _workflows():
        row = _audit_rows_for(audit, workflow.stem).lower()
        for dotted, bracketed in pattern.findall(workflow.read_text(encoding="utf-8")):
            name = dotted or bracketed
            total += 1
            if name.lower() not in row:
                unrecorded.append(f"{workflow.name}:{name}")

    assert total, "no secrets referenced by any workflow; the pattern probably stopped matching"
    assert not unrecorded, (
        "secrets a workflow reads that its own audit row does not name: "
        f"{', '.join(sorted(set(unrecorded)))} — record the identity in that row in "
        "docs/adr/0002-automation-identity.md"
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
