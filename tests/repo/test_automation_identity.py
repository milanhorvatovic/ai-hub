"""Structural contracts for the identities automation acts as.

The rule and the per-workflow audit live in `docs/adr/0002-automation-identity.md`.
These pin the things about it that go stale silently: a job gaining default-token write
access without anyone re-reading the rule, a secret-backed identity arriving that no
audit row accounts for, a workflow arriving that the audit never covered, and the job
guards that keep the PR-triggered minting workflow acting only on Dependabot's own
pull requests.

The two job-level pins answer different questions, stated once in the ADR's "Two
pins, two questions": the event-authoring set pins which jobs hold a write scope able
to author an event other workflows could be triggered by, and the write inventory pins
every scope any job grants the default token, exempt ones included. Neither is the
whole answer to which jobs act as something — a `permissions:` block governs only the
default token — so the secret check pairs every secret-backed identity with the audit
row that names it.

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

# The jobs holding default-token write scopes able to author events — the set the
# cascade rule turns on — and why each earns it: uploading release assets, uploading
# the catalog manifest. The release-please job is deliberately absent — it writes
# through a minted App token, so its default token stays on the read-only floor.
_EVENT_AUTHORING_JOBS = {
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
# an Actions run, so no workflow exists for the suppression rule to withhold. Checked
# 2026-08-12 against GitHub's "Events that trigger workflows" reference, which has no
# code_scanning_alert entry while the webhook reference does. That list is GitHub's to
# grow, so doubt is answered by re-checking it there, dated — not by re-arguing here —
# and a scope it gains moves out of this set. Exemption is routing, not invisibility:
# every scope here is still counted by the write inventory below, because a privilege
# is a privilege whether or not its events cascade — conflating those two questions is
# what the rename in this file's history was correcting.
_NON_AUTHORING_SCOPES = frozenset({"security-events", "id-token", "attestations"})

# Every write scope any job grants the default token — the privilege question, with the
# exempt scopes counted. `id-token: write` is why the two pins are separate: the OIDC
# token it mints proves this repository's identity to services that grant access on
# their side, a larger capability than most authoring scopes, and a set scoped to
# cascade alone would report it as no grant at all.
_WRITE_GRANTS = {
    ("codeql.yml", "analyze"): frozenset({"security-events"}),
    ("release-please.yml", "bundle"): frozenset(
        {"contents", "id-token", "attestations"}
    ),
    ("release-please.yml", "catalog-publish"): frozenset(
        {"contents", "id-token", "attestations"}
    ),
    ("scorecard.yml", "analyze"): frozenset({"security-events", "id-token"}),
}

# The one place an outside contributor's input meets a write-capable identity is a
# workflow that both triggers on a pull_request event and can mint the automation App
# token. Its trust model, stated where that workflow declares its trigger, is held here
# as four pins: every job binds itself to Dependabot as the PR author and to a head
# branch inside this repository, the workflow checks out nothing, and no PR-triggered
# workflow delegates a job to a reusable workflow the first three cannot see into.
# Each is one edit away from silently widening, and nothing else checks them.
_DEPENDABOT_LOGINS = frozenset({"dependabot[bot]", "app/dependabot"})
_SAME_REPO_COMPARISON = (
    "github.event.pull_request.head.repo.full_name == github.repository"
)
_AUTOMATION_KEY = "OSS_AUTOMATION_BOT_PRIVATE_KEY"
_PR_AUTHOR_COMPARISON = re.compile(
    r"^github\.event\.pull_request\.user\.login == '([^']*)'$"
)

_ANY_GRANT = frozenset({"*"})
_CODE_SPAN = re.compile(r"`([^`]+)`")
_EXPRESSION = re.compile(r"\$\{\{(.+?)\}\}", re.S)
# Expression context names are case-insensitive — `${{ Secrets.X }}` reads the same
# store — so both matchers compile that way; every consumer normalizes the captured
# name itself before comparing.
_NAMED_SECRET = re.compile(
    r"""secrets(?:\.([A-Za-z_]\w*)|\[\s*['"]([A-Za-z_]\w*)['"]\s*\])""",
    re.IGNORECASE,
)
_ANY_SECRETS_MENTION = re.compile(r"\bsecrets\b", re.IGNORECASE)


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
            str(scope)
            for scope, level in node.items()
            if level == "write" and scope not in exempt
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


def _section(adr: str, heading: str) -> str:
    """One `###` section of the ADR, alone — not the whole document.

    Asking whether the file mentions something anywhere would pass on a name that
    appears only in prose outside the section that vouches for it, which is not what
    being recorded there means.
    """
    _, _, after = adr.partition(heading)
    section, _, _ = after.partition("\n### ")
    assert (
        section.strip()
    ), f"the ADR section {heading!r} was not found under its heading"
    return section


def _audit_rows_for(audit: str, stem: str) -> str:
    """The audit rows naming `stem`, joined — the rows that speak for one workflow.

    Scoping to the section is not enough on its own: asking whether a secret appears
    anywhere in the audit passes when some other workflow's row happens to name it, so
    two independently true facts stand in for the pairing nobody checked.
    """
    rows = [
        row for row in audit.splitlines() if row.startswith("|") and f"`{stem}`" in row
    ]
    return "\n".join(rows)


def _events(document: dict) -> frozenset[str]:
    """The event names a workflow triggers on.

    YAML 1.1 reads a bare `on` key as the boolean True, so the trigger block is looked
    up under both spellings rather than trusting either one.
    """
    trigger = document.get("on", document.get(True))
    if isinstance(trigger, str):
        return frozenset({trigger})
    if isinstance(trigger, list | dict):
        return frozenset(str(event) for event in trigger)
    return frozenset()


def _operands(expression: str, operator: str) -> list[str]:
    """Top-level operands of one boolean operator in a GitHub expression, normalized.

    Depth- and quote-aware rather than a split: an operator inside parentheses or a
    quoted string joins nothing at this level, and reading it as if it did would let a
    comparison demoted behind `||` keep passing a check that wants a conjunct.
    """
    operands, start, index, depth, quoted = [], 0, 0, 0, False
    while index < len(expression):
        char = expression[index]
        if quoted:
            quoted = char != "'"
        elif char == "'":
            quoted = True
        elif char in "([":
            depth += 1
        elif char in ")]":
            depth -= 1
        elif depth == 0 and expression.startswith(operator, index):
            operands.append(expression[start:index])
            index += len(operator)
            start = index
            continue
        index += 1
    operands.append(expression[start:])
    return [" ".join(operand.split()) for operand in operands]


def _unwrapped(conjunct: str) -> str:
    """The conjunct without an enclosing parenthesis pair, when one wraps it whole.

    Quote-aware for the same reason `_operands` is: a parenthesis inside a quoted
    string nests nothing, and counting it would read a wrapped guard that mentions
    `')'` as ending early — opaque to the conjunct checks despite binding.
    """
    while conjunct.startswith("(") and conjunct.endswith(")"):
        depth, quoted = 0, False
        for index, char in enumerate(conjunct):
            if quoted:
                quoted = char != "'"
            elif char == "'":
                quoted = True
            elif char == "(":
                depth += 1
            elif char == ")":
                depth -= 1
            if depth == 0 and index < len(conjunct) - 1:
                return conjunct
        conjunct = conjunct[1:-1].strip()
    return conjunct


def _conjuncts(expression: str) -> list[str]:
    """Every `&&` operand that binds the whole expression, parentheses flattened.

    `(A && B) && C` and `(A && B && C)` bind A, B, and C exactly as `A && B && C`
    does, so a pair wrapping an operand is removed and the operand re-split rather
    than read as one opaque conjunct the guard checks would then miss.

    A bare `||` ends the decomposition instead: `&&` binds tighter, so
    `A || B && C` means `A || (B && C)` and C binds nothing globally. Splitting on
    `&&` anyway would report C as a conjunct — the exact bypass where deleting the
    author group's parentheses keeps both pins green — so a disjunction is one
    opaque operand, and the guard only passes in its parenthesized spelling.
    """
    if len(_operands(expression, "||")) > 1:
        return [" ".join(expression.split())]
    conjuncts = []
    for operand in _operands(expression, "&&"):
        unwrapped = _unwrapped(operand)
        if unwrapped == operand:
            conjuncts.append(operand)
        else:
            conjuncts.extend(_conjuncts(unwrapped))
    return conjuncts


def _pull_request_minting_workflows() -> list[tuple[Path, dict]]:
    """Workflows that can mint the automation App token from a pull_request event.

    Derived rather than named so a future workflow that reaches the key from a
    pull_request or pull_request_target trigger meets the guard pins the day it lands,
    not the day someone re-reads it. Reads one document at a time, which is sound only
    while the delegation pin below keeps reusable-workflow calls off PR triggers.
    """
    minting = []
    for workflow in _workflows():
        document = _document(workflow)
        if not _events(document) & {"pull_request", "pull_request_target"}:
            continue
        # Secret names and context property lookups are both case-insensitive on
        # GitHub, so `secrets.oss_automation_bot_private_key` reads the same key —
        # compared uppercased, or that spelling would evade the derivation.
        named = {
            (dotted or bracketed).upper()
            for expression in _expressions(document)
            for dotted, bracketed in _NAMED_SECRET.findall(expression)
        }
        if _AUTOMATION_KEY in named:
            minting.append((workflow, document))
    return minting


def test_every_workflow_declares_a_read_only_floor() -> None:
    for workflow in _workflows():
        document = _document(workflow)
        assert (
            "permissions" in document
        ), f"{workflow.name}: no workflow-wide permissions floor"
        # No exemption here, unlike the job audit below: the floor rule is that a
        # workflow grants nothing repo-wide, so `id-token: write` at the top would hand
        # OIDC to every job in the file even though it authors no event.
        assert not _grants(
            document["permissions"], exempt=frozenset()
        ), f"{workflow.name}: the workflow-wide floor grants write; elevate per job instead"


def test_only_the_release_jobs_hold_event_authoring_write_scopes() -> None:
    # Named for its contract: the cascade question, so the exempt scopes are invisible
    # here on purpose and the inventory test below counts them. A `permissions:` block
    # governs the default token and nothing else, so this cannot be the check for
    # "which jobs may author events" either — both Dependabot workflows author reviews,
    # auto-merge state, and a synchronize event through a secret-backed identity, and
    # no permissions block mentions it. That half belongs to the secret guard below,
    # which pairs every secret a workflow reads with the audit row naming it. Derived
    # from the tree rather than counted, so a newly elevated job fails here and sends
    # its author to the rule.
    authoring = {
        (workflow.name, name)
        for workflow in _workflows()
        for name, job in _jobs(_document(workflow)).items()
        if _grants((job or {}).get("permissions"), _NON_AUTHORING_SCOPES)
    }

    assert authoring == _EVENT_AUTHORING_JOBS, (
        "the event-authoring set changed: a job's default token gained or lost write "
        "access able to author an event other workflows can be triggered by. The "
        "identity it acts as is a decision, so read docs/adr/0002-automation-identity.md "
        f"before updating this set (added: {sorted(authoring - _EVENT_AUTHORING_JOBS)}, "
        f"removed: {sorted(_EVENT_AUTHORING_JOBS - authoring)})"
    )


def test_every_write_scope_a_job_holds_is_pinned() -> None:
    # Named for the other contract: privilege rather than cascade. This reads what the
    # default token may write at all, so a job gaining `id-token: write` fails here as
    # the deliberate edit it is without being mislabeled as event-authoring. Derived
    # with no exemption — the inventory and the exemption list must never share a
    # blind spot.
    granted = {
        (workflow.name, name): grants
        for workflow in _workflows()
        for name, job in _jobs(_document(workflow)).items()
        if (grants := _grants((job or {}).get("permissions"), exempt=frozenset()))
    }

    differing = [
        f"{workflow}:{job} holds {sorted(granted.get((workflow, job), ()))} "
        f"but pins {sorted(_WRITE_GRANTS.get((workflow, job), ()))}"
        for workflow, job in sorted(set(granted) | set(_WRITE_GRANTS))
        if granted.get((workflow, job)) != _WRITE_GRANTS.get((workflow, job))
    ]
    assert not differing, (
        "the write inventory changed: this is the privilege pin, not the "
        "event-authoring set — it counts every scope the default token can write, "
        "exempt ones included. A new grant is a decision, so read "
        "docs/adr/0002-automation-identity.md and update the inventory and its ADR "
        f"table together ({'; '.join(differing)})"
    )


def test_each_exempt_scope_is_counted_by_the_inventory() -> None:
    # The division of labor, held per exempt scope: the event-authoring read may skip a
    # scope only while the inventory read counts it. If either half fails, the
    # exemption has stopped being routing and become a hole — a write the authoring set
    # skips and the inventory misses would be a grant no guard sees.
    for scope in sorted(_NON_AUTHORING_SCOPES):
        declaration = {scope: "write"}
        assert not _grants(declaration, _NON_AUTHORING_SCOPES), (
            f"the event-authoring read no longer exempts `{scope}: write`; if GitHub's "
            "trigger list grew an event for it, move the scope out of the exemption — "
            "otherwise fix the read"
        )
        assert _grants(declaration, exempt=frozenset()) == {scope}, (
            f"the inventory read does not count `{scope}: write`; an exempt scope must "
            "still be a counted grant"
        )


def test_the_adr_inventory_table_matches_the_pinned_grants() -> None:
    # The inventory pin's failure message says to update the set and the ADR's table
    # together; this is what makes "together" a contract rather than an instruction.
    # Both directions are the same defect — a grant the table does not document, and a
    # row documenting a grant no job holds, are each a hand-written copy of a
    # measurement drifting from the measurement.
    section = _section(_ADR.read_text(encoding="utf-8"), "### Two pins, two questions")

    documented = set()
    for row in section.splitlines():
        cells = [cell for cell in row.split("|") if cell.strip()]
        if len(cells) < 2 or not _CODE_SPAN.search(cells[0]):
            continue
        stem, *jobs = _CODE_SPAN.findall(cells[0])
        documented |= {
            (stem, job, scope) for job in jobs for scope in _CODE_SPAN.findall(cells[1])
        }

    pinned = {
        (Path(workflow).stem, job, scope)
        for (workflow, job), scopes in _WRITE_GRANTS.items()
        for scope in scopes
    }
    assert documented == pinned, (
        "the ADR's inventory table and the pinned write grants disagree — they change "
        "together, per docs/adr/0002-automation-identity.md "
        f"(undocumented: {sorted(pinned - documented)}, "
        f"stale rows: {sorted(documented - pinned)})"
    )


def test_every_secret_a_workflow_uses_is_named_in_its_own_audit_row() -> None:
    # A new secret is a new identity, which is the thing the ADR exists to decide — and
    # the row is the unit, not the table: a secret named somewhere in the audit says
    # nothing about the workflow now reading it, so each is checked against the rows
    # that speak for it.
    audit = _section(
        _ADR.read_text(encoding="utf-8"), "### What each workflow uses today"
    )

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
    assert (
        total
    ), "no secrets referenced by any workflow; the pattern probably stopped matching"
    assert not unrecorded, (
        "secrets a workflow reads that its own audit row does not name: "
        f"{', '.join(sorted(set(unrecorded)))} — record the identity in that row in "
        "docs/adr/0002-automation-identity.md"
    )


def test_the_audit_covers_every_workflow() -> None:
    # An audit is only as good as its coverage, and a new workflow is exactly what it
    # would miss. Each is named by its stem, in backticks, inside the audit itself.
    audit = _section(
        _ADR.read_text(encoding="utf-8"), "### What each workflow uses today"
    )
    missing = [w.name for w in _workflows() if f"`{w.stem}`" not in audit]

    assert not missing, (
        f"workflows absent from the ADR's audit: {', '.join(missing)} — add a row to "
        "'What each workflow uses today' in docs/adr/0002-automation-identity.md"
    )


def test_every_pr_triggered_minting_job_acts_only_on_dependabots_own_prs() -> None:
    # An outside contributor can open a pull request but cannot author one as
    # Dependabot and cannot place its head branch inside this repository, so these two
    # job-level conditions are the whole reason outsider PRs never reach the
    # token-bearing steps. Appearing somewhere in the expression is not enough — a
    # comparison demoted behind `||` is still present while no longer binding — so
    # each must stand as its own top-level conjunct.
    minting = _pull_request_minting_workflows()
    assert minting, (
        "no pull_request-triggered workflow reads the automation key anymore; the "
        "derivation stopped matching, so fix it before trusting these guards"
    )
    for workflow, document in minting:
        for name, job in _jobs(document).items():
            condition = (job or {}).get("if")
            assert isinstance(condition, str), (
                f"{workflow.name}:{name}: no job-level `if:` — a job in a workflow "
                "that can mint the automation token on a pull_request event must "
                "bind itself to Dependabot's own PRs"
            )
            conjuncts = _conjuncts(condition)
            assert _SAME_REPO_COMPARISON in conjuncts, (
                f"{workflow.name}:{name}: the same-repository comparison is not a "
                "top-level conjunct of the job guard, so a fork's PR could reach the "
                "token-bearing steps"
            )

            author_logins = None
            for conjunct in conjuncts:
                comparisons = [
                    _PR_AUTHOR_COMPARISON.match(_unwrapped(part))
                    for part in _operands(conjunct, "||")
                ]
                if comparisons and all(comparisons):
                    author_logins = {match.group(1) for match in comparisons}
                    break
            assert author_logins is not None, (
                f"{workflow.name}:{name}: no top-level conjunct restricts the PR "
                "author, so any contributor's PR would reach the token-bearing steps"
            )
            assert author_logins <= _DEPENDABOT_LOGINS, (
                f"{workflow.name}:{name}: the author guard admits "
                f"{sorted(author_logins - _DEPENDABOT_LOGINS)} — widening who the "
                "policy acts for is a decision, so update the pinned logins with it"
            )


def test_pr_triggered_minting_workflows_check_out_nothing() -> None:
    # The other half of the trust model stated at that workflow's trigger: it stays on
    # pull_request and never checks out code, so a poisoned bump has nothing to execute
    # inside the job holding the token. A checkout of any ref trips this on purpose —
    # the invariant worth pinning is the one with no exceptions to reason about.
    for workflow, document in _pull_request_minting_workflows():
        # Action slugs resolve case-insensitively — `Actions/Checkout@…` runs the
        # same action — so the comparison lowercases what the step declares.
        checkouts = [
            f"{workflow.name}:{name}"
            for name, job in _jobs(document).items()
            for step in (job or {}).get("steps") or []
            if str((step or {}).get("uses") or "").partition("@")[0].lower()
            == "actions/checkout"
        ]
        assert not checkouts, (
            "checkout steps in a token-minting pull_request workflow: "
            f"{', '.join(checkouts)} — this workflow's trust model is that it checks "
            "out nothing; run checkouts in a separate workflow with no App key"
        )


def test_pr_triggered_workflows_delegate_no_jobs_to_reusable_workflows() -> None:
    # The minting derivation correlates a PR trigger with a key reference inside one
    # document, and a reusable-workflow call is the edge that breaks that assumption:
    # a local callee can read the key in its own document — an environment secret
    # needs no mention in the caller — while carrying no PR trigger, so caller and
    # callee each look innocent and the token-bearing path sits outside every pin
    # above; a remote callee's steps are not in the tree for the checkout pin to read
    # at all. No workflow delegates a job today, so the edge is rejected outright — a
    # legitimate call arrives together with the transitive traversal that makes its
    # closure visible to these pins.
    delegating = []
    for workflow in _workflows():
        document = _document(workflow)
        if not _events(document) & {"pull_request", "pull_request_target"}:
            continue
        delegating += [
            f"{workflow.name}:{name} uses {job['uses']}"
            for name, job in _jobs(document).items()
            if "uses" in (job or {})
        ]
    assert not delegating, (
        f"reusable-workflow calls in PR-triggered workflows: {', '.join(delegating)} "
        "— the minting pins read one document at a time, so a call edge moves the "
        "token-bearing path outside their sight; teach "
        "_pull_request_minting_workflows to traverse the closure before admitting one"
    )
