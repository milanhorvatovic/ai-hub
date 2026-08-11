"""Structural contracts for the identities automation acts as.

The rule and the per-workflow audit live in `docs/adr/0002-automation-identity.md`.
These pin the things about it that go stale silently: a job gaining default-token write
access without anyone re-reading the rule, a secret-backed identity arriving that no
audit row accounts for, and a workflow arriving that the audit never covered. The two
identity checks are complements — a `permissions:` block governs only the default token,
so it can never be the whole answer to which jobs act as something.

These read the parsed document rather than its text. An earlier version matched YAML by
regex and five review rounds each found a legal spelling it could not see — quoted keys,
flow mappings, trailing comments, name casing, aliases — every one of them a grant the
guard reported as absent. The spellings are not a list that can be finished, so the fix
is to stop reading spellings: `safe_load` resolves aliases, drops comments, and makes
quoting and flow-versus-block style stop existing before any check runs.
"""

import re
from pathlib import Path

import yaml

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
#
# `security-events` belongs here for a reason worth writing down, because it reads like
# it should not. Uploading results does create code-scanning alerts, and
# `code_scanning_alert` is a real webhook — but it is not one of the events that start
# an Actions run, so no workflow exists for the suppression rule to withhold. The scope
# is a privilege; this guard is about identity and cascade, and conflating the two is
# what the rename in this file's history was correcting.
_NON_AUTHORING_SCOPES = frozenset({"security-events", "id-token", "attestations"})

_ANY_GRANT = frozenset({"*"})
_EXPRESSION = re.compile(r"\$\{\{(.+?)\}\}", re.S)
_NAMED_SECRET = re.compile(r"""secrets(?:\.([A-Za-z_]\w*)|\[\s*['"]([A-Za-z_]\w*)['"]\s*\])""")
_ANY_SECRETS_MENTION = re.compile(r"\bsecrets\b")


def _workflows() -> list[Path]:
    found = sorted(_WORKFLOW_DIR.glob("*.y*ml"))
    assert found, "no workflow files found"
    return found


def _document(workflow: Path) -> dict:
    parsed = yaml.safe_load(workflow.read_text(encoding="utf-8"))
    assert isinstance(parsed, dict), f"{workflow.name}: not a mapping at the top level"
    return parsed


def _jobs(document: dict) -> dict:
    jobs = document.get("jobs") or {}
    assert isinstance(jobs, dict) and jobs, "no jobs found"
    return jobs


def _grants(node: object, exempt: frozenset[str]) -> frozenset[str]:
    """Scopes granted `write` by a parsed `permissions:` value, minus the exempt ones.

    A shape this does not recognize returns a grant rather than an absence: an
    unreadable declaration is the case where a guard about identity must be noisy.
    """
    if node is None:
        return frozenset()
    if isinstance(node, str):
        if node == "write-all":
            return _ANY_GRANT
        return frozenset() if node in {"read-all", "none"} else _ANY_GRANT
    if isinstance(node, dict):
        return frozenset(
            str(scope) for scope, level in node.items() if level == "write" and scope not in exempt
        )
    return _ANY_GRANT


def _expressions(node: object) -> list[str]:
    """Every `${{ … }}` expression in the document, wherever it is nested."""
    if isinstance(node, str):
        return [match.group(1) for match in _EXPRESSION.finditer(node)]
    if isinstance(node, dict):
        return [found for value in node.values() for found in _expressions(value)]
    if isinstance(node, list):
        return [found for item in node for found in _expressions(item)]
    return []


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
        document = _document(workflow)
        assert "permissions" in document, f"{workflow.name}: no workflow-wide permissions floor"
        # No exemption here, unlike the job audit below: the floor rule is that a
        # workflow grants nothing repo-wide, so `id-token: write` at the top would hand
        # OIDC to every job in the file even though it authors no event.
        assert not _grants(document["permissions"], exempt=frozenset()), (
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
    elevated = {
        (workflow.name, name)
        for workflow in _workflows()
        for name, job in _jobs(_document(workflow)).items()
        if _grants((job or {}).get("permissions"), _NON_AUTHORING_SCOPES)
    }

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
    # that speak for it.
    audit = _audit_section(_ADR.read_text(encoding="utf-8"))

    total, unrecorded, inherited, unauditable = 0, [], [], []
    for workflow in _workflows():
        document = _document(workflow)
        row = _audit_rows_for(audit, workflow.stem).lower()

        # `secrets: inherit` hands a called workflow everything at once and names none
        # of it, so it is the one form that could pass this guard by having nothing to
        # check. An audit that lists identities by name cannot record it.
        inherited += [
            f"{workflow.name}:{name}"
            for name, job in _jobs(document).items()
            if (job or {}).get("secrets") == "inherit"
        ]

        for expression in _expressions(document):
            named = _NAMED_SECRET.findall(expression)
            for dotted, bracketed in named:
                name = dotted or bracketed
                total += 1
                # The row must name the secret as its own code span. A substring test
                # would accept `TOKEN` against a row documenting `GITHUB_TOKEN` —
                # passing exactly the new identity this exists to catch.
                if f"`{name.lower()}`" not in row:
                    unrecorded.append(f"{workflow.name}:{name}")

            # Anything else that reaches the context reads secrets this cannot name: a
            # dynamic index like `secrets[env.NAME]`, or a whole-context read such as
            # `toJSON(secrets)`. Both choose an identity no audit row could record.
            # The literal reads are removed first rather than merely counted, because a
            # mixed expression — one literal beside one dynamic index — would otherwise
            # be excused by the half that is readable.
            if _ANY_SECRETS_MENTION.search(_NAMED_SECRET.sub("", expression)):
                unauditable.append(f"{workflow.name}: {expression.strip()}")

    assert not inherited, (
        f"jobs passing secrets by inheritance: {', '.join(inherited)} — the audit "
        "records identities by name, and `secrets: inherit` names none"
    )
    assert not unauditable, (
        f"secret reads whose name is not a literal: {', '.join(unauditable)} — the "
        "identity is chosen at run time, so no audit row can name it"
    )
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
