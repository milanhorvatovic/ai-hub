"""Contract tests for the commit verb and the SPLIT mode behind it.

The verb is the first surface in this skill that applies rather than proposes,
so the tests that matter are the ones holding the boundary: that polarity is a
property of the surface and not of the capability, that the conversational path
cannot reach the applying half under any flag, and that a guard veto outranks
the verb. Those three are what make an apply default safe to ship, and each is
prose until something checks it.

SPLIT itself is pinned as a mode inside `commit-message` rather than a sibling
capability — the design call the packet settled, and the one a later edit is
most likely to undo by "promoting" it. The eligibility floor gets the same
treatment: it was measured as a veto, and a veto that quietly becomes a trigger
is the regression that turns the verb into an over-eager splitter.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[3]

# The six tree states the router's `commit` dispatch table must route. Each is
# keyed by a phrase unique to its own row: an earlier draft matched "staged",
# which the first three rows all carry, so deleting two of them left the check
# green. No key may be a substring of another row's text.
_DISPATCH_STATES = (
    ("single-concern staged", "one concern"),
    ("mixed staged", "mixed concerns"),
    ("fixup-shaped", "fixup-shaped"),
    ("dirty but unstaged", "Nothing staged, tree dirty"),
    ("clean tree", "Clean tree"),
    ("mid-operation", "Mid-rebase"),
)

# Each veto row names a guard that has to exist elsewhere in the tree. Pinning
# the pair is what stops the table becoming self-referential prose: a veto that
# cites a catalog entry nobody ships fires on nothing.
_VETO_ANCHORS = (
    ("secret", "secret-patterns.md", _REPO_ROOT / "skills/git-toolkit/references/secret-patterns.md", None),
    ("force-push", "force-push-impact.md", _REPO_ROOT / "skills/git-toolkit/references/force-push-impact.md", "Force-Push Impact"),
    ("mixed-scope", "commit-smells.md", _REPO_ROOT / "skills/git-toolkit/references/commit-smells.md", "### `mixed-scope`"),
)


def _section(text: str, heading: str) -> str:
    """The body of a `## <heading>` section, up to the next `## `."""
    assert heading in text, f"section {heading!r} not found"
    return text.split(heading, 1)[1].split("\n## ", 1)[0]


def _rows(table_text: str) -> list[str]:
    """Markdown table rows, minus the header and the `| --- |` separator."""
    return [
        line
        for line in table_text.splitlines()
        if line.startswith("|") and not re.match(r"^\|[\s|-]+\|$", line)
    ]


@pytest.fixture(scope="session")
def router(skill_root: Path) -> str:
    return (skill_root / "SKILL.md").read_text(encoding="utf-8")


@pytest.fixture(scope="session")
def commit_message_md(capabilities_dir: Path) -> str:
    return (capabilities_dir / "commit-message" / "capability.md").read_text(encoding="utf-8")


@pytest.fixture(scope="session")
def arguments(router: str) -> str:
    return _section(router, "## Arguments")


@pytest.fixture(scope="session")
def split_mode(commit_message_md: str) -> str:
    return _section(commit_message_md, "## SPLIT mode workflow")


def test_split_is_a_mode_not_a_capability(
    capabilities_dir: Path, commit_message_md: str
) -> None:
    """SPLIT composes WRITE internally, which a sibling capability could not do.

    A `commit-split` capability would collide with commit-message's trigger cell
    — "about to commit staged changes" is one lifecycle moment — and its
    authoring half would have to either duplicate WRITE or reference a sibling,
    which this skill's self-sufficiency principle and the foundry audit both
    forbid. So the mode table is where SPLIT must appear.
    """
    assert not (capabilities_dir / "commit-split").exists(), (
        "SPLIT landed as a sibling capability; it composes WRITE and must stay a mode"
    )
    modes = _section(commit_message_md, "## Mode detection")
    row = next((r for r in _rows(modes) if "**SPLIT**" in r), None)
    assert row, "Mode detection has no SPLIT row"
    assert "N=1" in modes, (
        "the mode table does not state that WRITE is SPLIT's N=1 case, so nothing "
        "stops a future edit routing single-concern trees through a splitter"
    )


def test_router_carries_the_verb_grammar(arguments: str) -> None:
    """The grammar belongs to the router: routing is the router's job, and only
    capability-to-capability reference is banned."""
    assert "/git-toolkit <verb>" in arguments, (
        "the Arguments section does not state the verb grammar"
    )


@pytest.mark.parametrize(("label", "phrase"), _DISPATCH_STATES)
def test_commit_dispatch_routes_every_tree_state(
    label: str, phrase: str, arguments: str
) -> None:
    """Each state the verb can meet has a named route.

    An unrouted state is not a gap the agent notices — it is a state where the
    verb improvises, and the two that matter most are the ones where the right
    answer is to do nothing (clean tree, mid-rebase).
    """
    table = arguments.split("### `commit` dispatch", 1)
    assert len(table) == 2, "Arguments has no `commit` dispatch section"
    assert any(phrase in row for row in _rows(table[1])), (
        f"the dispatch table has no row for the {label} state (looked for {phrase!r})"
    )


def test_clean_and_mid_operation_states_propose_nothing(arguments: str) -> None:
    """The two states whose correct route is to stop.

    Checked separately from the row's existence because a row that exists and
    routes to a proposal is worse than no row: it looks handled.
    """
    rows = _rows(arguments.split("### `commit` dispatch", 1)[1])
    for phrase in ("Clean tree", "Mid-rebase"):
        row = next(r for r in rows if phrase in r)
        assert "stop" in row.lower(), (
            f"the {phrase!r} row does not stop; a verb that proposes against an "
            f"unfinished tree proposes against a state it cannot read: {row!r}"
        )


def test_apply_polarity_is_a_property_of_the_surface(arguments: str) -> None:
    """One capability, two polarities, decided by how the invocation arrived.

    This is the whole safety argument for an apply default, so it is asserted
    per row rather than as a keyword sweep over the section: an earlier draft
    searched the section for "dry-run" and "propose" and stayed green after the
    conversational row was deleted, because the other two rows carry both words.
    """
    table = arguments.split("### Verb polarity", 1)
    assert len(table) == 2, "Arguments has no Verb polarity section"
    rows = _rows(table[1])

    verb = next((r for r in rows if "/git-toolkit commit" in r), None)
    assert verb, "no polarity row for the explicit commit verb"
    assert "**applies**" in verb and "--dry-run" in verb, (
        f"the commit verb's row does not pair an apply default with --dry-run: {verb!r}"
    )

    conversational = next((r for r in rows if "Conversational" in r), None)
    assert conversational, "no polarity row for the conversational trigger path"
    assert "**proposes**" in conversational, (
        f"the conversational row does not default to proposing: {conversational!r}"
    )
    assert "no flag" in conversational.lower(), (
        "the conversational row does not close the flag path, so --apply on a "
        f"conversationally-triggered invocation is undefined rather than refused: {conversational!r}"
    )

    outward = next((r for r in rows if "outward" in r.lower()), None)
    assert outward, "no polarity row for outward verbs"
    assert "**proposes**" in outward and "--apply" in outward, (
        f"outward verbs do not default to proposing with an explicit opt-in: {outward!r}"
    )


def test_push_is_never_bundled_into_commit(arguments: str) -> None:
    """The one bundling the polarity table exists to forbid.

    `commit` earns its apply default on local reversibility; a push spends that
    argument entirely, and bundling it would let one typed verb do a thing no
    verb named.
    """
    assert re.search(r"never bundles a push|never bundled into", arguments), (
        "Arguments does not state that the commit verb never bundles a push"
    )


def test_guards_outrank_the_verb_at_router_level(arguments: str) -> None:
    """Precedence is the router's rule; the veto list is the capability's.

    Stated here because a capability that owned both could quietly grant itself
    an exception, and because the next verb to gain a polarity inherits the
    precedence without re-deriving it.
    """
    section = arguments.split("### Guards outrank the verb", 1)
    assert len(section) == 2, "Arguments does not carry the guard-precedence rule"
    body = section[1].lower()
    assert "no flag overrides a veto" in body, (
        "the precedence rule does not close the flag path around a veto"
    )
    assert "permission" in body, (
        "the precedence rule does not name the harness permission layer as the "
        "outer gate, so the skill reads as if its own polarity were the boundary"
    )


@pytest.mark.parametrize(("label", "reference", "path", "anchor"), _VETO_ANCHORS)
def test_each_veto_cites_a_guard_that_exists(
    label: str, reference: str, path: Path, anchor: str | None, split_mode: str
) -> None:
    """Every veto row names a guard, and every named guard is really shipped.

    The pairing is the point. A veto table checked only against itself passes
    while citing a catalog entry that was renamed or deleted, which is exactly
    the failure that looks like a pass — the table still reads as three guards.
    """
    section = split_mode.split("### 8. Guard vetoes", 1)
    assert len(section) == 2, "SPLIT mode has no guard-veto section"
    table = section[1].split("###", 1)[0]
    # Match the row's first cell, not the row. The force-push veto names the
    # `mixed-scope` repair path as the route by which it inherits a rewrite, so
    # a whole-row search for "mixed-scope" picks the wrong row and then grades
    # it against the wrong reference — which is how this test first went green
    # on a table it was misreading.
    row = next((r for r in _rows(table) if label in r.split("|")[1].lower()), None)
    assert row, f"the veto table has no {label} row"
    assert reference in row, f"the {label} veto does not cite {reference}: {row!r}"
    assert "Proposal only" in row, (
        f"the {label} veto does not degrade to a proposal, so what it does when "
        f"it fires is unstated: {row!r}"
    )
    assert path.is_file(), f"the {label} veto cites {reference}, which does not exist"
    if anchor is not None:
        assert anchor in path.read_text(encoding="utf-8"), (
            f"the {label} veto cites {reference} for {anchor!r}, which that file does not carry"
        )


def test_a_veto_degrades_the_whole_invocation(commit_message_md: str) -> None:
    """Not the offending partition alone.

    A series applied minus one member is a state the user did not ask for and no
    message describes — worse than either applying all of it or none of it.
    """
    anti = _section(commit_message_md, "## Anti-patterns").lower()
    # "veto" plus "series" matches the tier entry too, which argues about
    # promotion rather than about application — the collision this test hit on
    # its first run. Select on the standing veto, which only this entry names.
    entry = next((ln for ln in anti.splitlines() if "veto stands" in ln), None)
    assert entry, (
        "Anti-patterns does not forbid applying a series while a veto stands"
    )
    assert "partition alone" in entry or "minus one" in entry, (
        f"the entry does not name partial application as the failure: {entry!r}"
    )


def test_the_eligibility_floor_is_a_veto_not_a_trigger(split_mode: str) -> None:
    """The measured decision, and the one most likely to be undone by accident.

    Path statistics select for wide changes, not for unrelated ones, so a floor
    promoted to a trigger fires the default tier on ordinary cross-package work
    — the over-eager splitter that stops people typing the verb.
    """
    tiers = split_mode.split("### 4.", 1)
    assert len(tiers) == 2, "SPLIT mode has no confidence-tier section"
    body = tiers[1].split("### 5.", 1)[0]
    assert "veto, not a trigger" in body, (
        "the tier section does not state that the eligibility floor only demotes"
    )
    assert "reading of the diff" in body, (
        "the default tier does not require reading the diff, so path statistics "
        "alone can promote a series to the default reply"
    )
    default_row = next(
        (r for r in _rows(body) if "Series by default" in r), None
    )
    assert default_row, "the tier table has no series-by-default row"
    assert "stand as a commit" in default_row, (
        "the default tier does not require each partition to stand alone, which "
        f"is the property the series exists to preserve: {default_row!r}"
    )


def test_the_thresholds_carry_their_provenance(split_mode: str) -> None:
    """A number without a provenance reads as a constant.

    The floor was calibrated on one repository's history — a skills monorepo,
    not a representative sample of anything — and a reader who cannot see that
    will treat 60% and 0.15 as facts about software rather than as a starting
    point. The fleet's currency rule is the same idea for tool versions.
    """
    body = split_mode.split("### 4.", 1)[1].split("### 5.", 1)[0]
    assert "one repository's" in body, (
        "the measured thresholds do not say what they were measured on, so they "
        "read as universal constants"
    )
    assert "rather than as constants" in body, (
        "the provenance is stated without saying what to do with it; a reader "
        "needs to know the numbers are a starting point, not a finding"
    )


def test_symbol_dependency_reaches_trees_without_symbols(split_mode: str) -> None:
    """This skill ships to prose and config repositories too.

    Stated as compiler-shaped, signal 3 is vacuous in a tree with no callers to
    find — which silently drops the strongest anti-split signal in exactly the
    repositories where paths are the only other thing to go on.
    """
    body = split_mode.split("### 3. Partition", 1)[1].split("### 4.", 1)[0]
    signal = body.split("3. **Symbol dependency.**", 1)[1].split("\n4.", 1)[0]
    assert "no symbols to follow" in signal, (
        "signal 3 assumes a tree with symbols, so it does nothing in prose, "
        "configuration, or schema repositories"
    )


def test_type_divergence_is_named_as_split_evidence(split_mode: str) -> None:
    """The signal that produced this change's own commit series.

    A pre-existing `fix` noticed while authoring a `feat` is two commits by the
    repository's own vocabulary, and bundling them files the fix under the
    feature in every generated changelog. It belongs in the default tier rather
    than among the path signals because it is evidence about reasons, which is
    the only kind that tier accepts.
    """
    body = split_mode.split("### 4.", 1)[1].split("### 5.", 1)[0]
    assert "different types" in body, (
        "the default tier does not name conventional-commit type divergence, the "
        "one reading of a pile that the repository's own vocabulary supplies"
    )
    assert "changelog" in body, (
        "the type-divergence signal does not say what bundling costs, so it reads "
        "as a stylistic preference rather than as lost information"
    )


def test_the_curation_rule_biases_to_one_commit(split_mode: str) -> None:
    """A staged subset of a dirty tree is an answer, not a question."""
    section = split_mode.split("### 2. The curation rule", 1)
    assert len(section) == 2, "SPLIT mode has no curation-rule section"
    body = section[1].split("### 3.", 1)[0]
    assert "--split" in body, (
        "the curation rule does not name the escape, so a user who does want the "
        "pile re-partitioned has no way to ask"
    )
    assert "git status --porcelain" in body, (
        "the curation rule does not say how curation is detected, so it is a "
        "principle with no input"
    )


def test_curation_reads_tracked_work_not_untracked_debris(split_mode: str) -> None:
    """The distinction dogfooding this mode against its own branch produced.

    The first draft counted any unstaged-or-untracked path as evidence that the
    user had partitioned by hand. Run against this repository it read a stray
    worktree directory and a leftover lockfile as deliberate curation and
    demoted a genuinely uncurated pile to N=1 — a rule that switches itself off
    in precisely the messy trees it exists for.
    """
    body = split_mode.split("### 2. The curation rule", 1)[1].split("### 3.", 1)[0]
    assert "`??`" in body, (
        "the curation rule does not say what untracked paths mean, so debris in "
        "the working tree reads as a hand-partitioned pile"
    )
    assert "not evidence" in body, (
        "the rule does not exclude untracked paths as evidence of curation"
    )
    for code in ("` M`", "`MM`"):
        assert code in body, (
            f"the rule does not name {code} as the tracked-work-left-behind signal "
            "it actually reads"
        )


def test_area_depth_follows_the_layout_not_a_fixed_level(split_mode: str) -> None:
    """Signal 1 and signal 2 have to agree about granularity, or they cancel.

    The same dogfood run caught this: a bucket pinned one level below the top
    resolved this repository's test tree to a level shallower than the mirror it
    pairs on, so a skill and its own tests scored as two unrelated areas — the
    exact false split signal 2 exists to prevent, produced by signal 1.
    """
    body = split_mode.split("### 3. Partition", 1)[1].split("### 4.", 1)[0]
    assert "rather than at a fixed level" in body, (
        "signal 1 fixes an area depth, which the pairing in signal 2 cannot "
        "follow when a repository nests its tests deeper than that"
    )
    pairing = body.split("2. **The test pairing.**", 1)[1].split("\n3.", 1)[0]
    # The instruction, not the word "depth": the sentence explaining why signal 1
    # fixes none also says "depth" twice, so a bare keyword survives deleting the
    # instruction it guards. Mutation found exactly that.
    assert "whatever depth the mirror holds" in pairing, (
        "the pairing rule does not tie itself to the depth of the mirror, so it "
        "matches only the layouts that happen to sit at signal 1's level"
    )


def test_series_messages_do_not_reference_each_other(split_mode: str) -> None:
    """Each commit is read alone in `git log`, and positions move under rebase."""
    section = split_mode.split("### 6. Author each message", 1)
    assert len(section) == 2, "SPLIT mode has no per-partition authoring section"
    body = section[1].split("### 7.", 1)[0]
    assert "No message may refer to another commit in the series" in body, (
        "nothing forbids a series message pointing at its siblings, so the series "
        "reads correctly only in the order it was proposed"
    )


def test_roles_score_but_never_count(split_mode: str) -> None:
    """The scope of role normalization, which is wrong in both easy directions.

    Normalize everywhere and two sibling packages collapse to one area, so a
    floor requiring two is structurally unreachable for the case a monorepo most
    wants split — and unreachable is worse than wrong, because the reading that
    decides everything else never gets to run. Normalize nowhere and a new
    package's wiring points score as unrelated, which is the failure the whole
    signal was introduced to fix. Both were shipped in turn before the rule was
    walked against a concrete pile.
    """
    body = split_mode.split("### 3. Partition", 1)[1].split("### 4.", 1)[0]
    signal = body.split("1. **Area.**", 1)[1].split("\n2.", 1)[0]
    assert "roles enter the scoring but never the counting" in signal, (
        "the rule does not separate scoring from counting, so role normalization "
        "either collapses the area count or leaves the lookup unnormalized"
    )
    assert "structurally unreachable" in signal, (
        "the rule does not say what collapsing the count costs, so the next edit "
        "that simplifies it has nothing to lose"
    )
    assert "same-role pair by its instances" in signal, (
        "a pair of same-role areas has no defined score, which is every "
        "two-package pile in a monorepo"
    )


def test_an_unknown_co_change_rate_does_not_clear_the_floor(split_mode: str) -> None:
    """Absence of evidence, one step later than where §1 already refuses it.

    Step 1 says a repository too young for a history must treat co-change as
    unknown rather than zero, because an empty history looks exactly like proof
    of unrelatedness. The floor then asks for a rate below a threshold, and left
    undefined an unknown reads as satisfying it — reinstating at the floor the
    error Step 1 refused at the input.
    """
    body = split_mode.split("### 4.", 1)[1].split("### 5.", 1)[0]
    assert "unknown co-change rate does not satisfy the floor" in body, (
        "the floor does not say what an unknown rate does, so a young repository "
        "clears the co-change clause by having no history to fail it"
    )
    assert "`--split`" in body, (
        "young repositories are given no route to a series at all; the forcing "
        "flag has to remain reachable where the floor cannot decide"
    )


def test_the_working_tree_path_supersedes_writes_staged_guard(split_mode: str) -> None:
    """WRITE stops on an empty index; the working-tree path arrives with one.

    Step 1's branch resolves the dirty-tree state and then hands each group to
    WRITE, whose own first step sanity-checks that staged changes exist and
    stops when they do not. Left unstated, the two steps cancel: the branch that
    exists to handle an empty index routes into a guard that refuses it.
    """
    body = split_mode.split("### 6. Author each message", 1)[1].split("### 7.", 1)[0]
    assert "superseded" in body, (
        "the authoring step does not say which WRITE step the working-tree path "
        "displaces, so that path routes into a guard that refuses its input"
    )
    assert "empty index" in body, (
        "the supersession does not name the condition it covers, so a reader "
        "cannot tell when the guard applies and when it does not"
    )


def test_the_scan_step_does_not_restate_writes_own(split_mode: str) -> None:
    """One home per rule, inside a mode as much as across files.

    SPLIT's contribution is the aggregate pass; the per-partition scan is WRITE's
    Step 6 running per partition, exactly as the rest of §6 arranges. Restating
    it as a separate action is a second copy that drifts, and this skill's own
    principle forbids that between references for the same reason.
    """
    body = split_mode.split("### 7. Pre-publication scans", 1)[1].split("### 8.", 1)[0]
    assert "WRITE's Step 6 already runs" in body, (
        "the scan step restates the per-partition scan instead of pointing at "
        "the WRITE step that performs it"
    )


def test_the_aggregate_scan_pass_is_justified(split_mode: str) -> None:
    """Two scan passes need a reason, or the second one gets optimized away.

    The reason is that a secret split across partitions is invisible in each,
    which is a property of the series and not of any member.
    """
    section = split_mode.split("### 7. Pre-publication scans", 1)
    assert len(section) == 2, "SPLIT mode has no pre-publication scan section"
    body = section[1].split("### 8.", 1)[0]
    for needle in (
        "../../references/secret-patterns.md",
        "../../references/publication-audience.md",
    ):
        assert needle in body, f"the scan step does not run {needle}"
    assert "not redundant" in body, (
        "the aggregate pass is stated without its reason, so it reads as a "
        "duplicate of the per-partition scan and will be dropped as one"
    )


def test_the_series_is_graded_before_it_is_applied(split_mode: str) -> None:
    """The gap an acceptance re-read found, and the one apply-by-default creates.

    WRITE can leave message validation to the reader, because a single proposal
    is read before it is run. A series under an applying verb is not: the same
    pass writes N messages and commits them, so without an explicit grading step
    the verb applies text nothing checked. Repair-first rather than report-first
    follows AMEND, which faces the same problem for the same reason.
    """
    body = split_mode.split("### 6. Author each message", 1)[1].split("### 7.", 1)[0]
    assert "REVIEW per-commit checks" in body, (
        "the authoring step does not validate its drafts against the REVIEW "
        "checks, so an applying verb commits messages nothing graded"
    )
    assert "wrap detection" in body, (
        "the pointer names the REVIEW checks without the detection above them, so "
        "a series body can be reflowed against a convention nothing established"
    )
    assert "repair-first" in body, (
        "the step does not say what happens on a failing check; a findings report "
        "is the wrong answer when the next thing the verb does is commit"
    )


def test_an_empty_index_drops_the_verb_to_a_proposal(split_mode: str) -> None:
    """The router dispatches this state; the capability has to implement it.

    The apply default is licensed by the user having staged something. With an
    empty index that signal does not exist — choosing what enters the commit is
    a different act from committing what someone picked — so the polarity does
    not carry over, and the router's row would otherwise route to a workflow
    whose first four commands all read `--cached`.
    """
    body = split_mode.split("### 1. Read the pile", 1)[1].split("### 2.", 1)[0]
    assert "nothing is staged" in body, (
        "SPLIT reads only the index, so the router's dirty-tree dispatch routes "
        "to a workflow with no input"
    )
    assert "git add" in body, (
        "the unstaged path does not produce staging recipes, which is the whole "
        "of what it can offer"
    )
    assert "drops to a proposal" in body, (
        "the unstaged path does not void the apply default, so the verb would "
        "stage on the user's behalf under a polarity that never covered it"
    )


def test_a_long_series_is_evidence_against_itself(split_mode: str) -> None:
    """The backstop the tiers do not provide.

    Confidence gates whether to split at all; nothing gated how far. An
    over-eager partition that clears the floor can still return eight groups,
    and eight commits from one session is the outcome that stops people typing
    the verb just as surely as a wrong split does.
    """
    body = split_mode.split("### 5. Order the series", 1)[1].split("### 6.", 1)[0]
    assert "evidence against itself" in body, (
        "nothing treats an implausibly long series as a partition failure"
    )
    assert "coarser" in body, (
        "the backstop does not say what to do about a long series, so it is an "
        "observation rather than a rule"
    )


def test_the_trigger_section_names_the_applying_path(router: str) -> None:
    """The router's own map of how it gets activated has to include the verb.

    Before this, "When to trigger" said activation cues live in two places only
    — the description and the routing tables — both of which are inferred
    activation that stops at a proposal. A reader following that section would
    never learn that a third path exists and that it is the only one able to
    run a command. Omitting the applying path from the map of activation paths
    is the most consequential kind of stale a router can carry.
    """
    section = _section(router, "## When to trigger")
    assert "verb the user types" in section, (
        "the trigger map does not list the typed verb, so the one activation "
        "path that can apply is absent from the section describing activation"
    )
    assert "stop at a proposal" in section, (
        "the trigger map does not say that the inferred paths cannot apply, so "
        "the three read as interchangeable"
    )


def test_no_router_surface_contradicts_the_apply_polarity(router: str) -> None:
    """Two surfaces of one file must not state opposite rules.

    The anti-pattern list said every state-changing command is surfaced for the
    user to run, which is what the principle above it said until the verb landed
    and stopped being true. The skill's own rule is that discovery and
    enforcement state the same rules; the same obligation holds inside one file.
    """
    anti = _section(router, "## Anti-patterns")
    entry = next((ln for ln in anti.splitlines() if "state-changing" in ln), None)
    assert entry, "the anti-pattern list no longer covers state-changing commands"
    assert "Outside an applying verb" in entry, (
        "the anti-pattern states an unconditional propose-only rule, contradicting "
        f"the apply polarity the principles define: {entry!r}"
    )
    assert "creates no branch" in entry, (
        "the entry does not bound what an applying verb may do, so the exception "
        f"it opens has no stated edge: {entry!r}"
    )


def test_the_walkthrough_demonstrates_the_silent_path(references_dir: Path) -> None:
    """The behaviour most likely to be regressed is the one that shows nothing.

    A splitter that stays quiet on single-concern work is the whole reason the
    tiers are conservative, and it is invisible by construction — so the
    onboarding walkthrough has to say the analysis ran and returned N=1, or the
    only example a reader meets is one where splitting never came up and they
    cannot tell that from the mode not existing.
    """
    text = (references_dir / "worked-example.md").read_text(encoding="utf-8")
    assert "N=1" in text, (
        "the walkthrough never shows the partition analysis running, so a reader "
        "cannot distinguish the silent path from an absent one"
    )
    assert "SPLIT" in text, "the walkthrough does not mention SPLIT at all"


def test_the_router_grammar_names_the_flags_it_owns(router: str) -> None:
    """Both flags, because the router claims to own the grammar.

    `--split` changes what the commit verb does, exactly as `--dry-run` does, so
    documenting one at router level and the other only inside the capability
    makes the router's own claim false and leaves a reader of the grammar unable
    to find half of it.
    """
    grammar = _section(router, "## Arguments").split("### Verb polarity", 1)[0]
    for flag in ("--dry-run", "--split"):
        assert flag in grammar, (
            f"the verb grammar does not name {flag}, which changes what a verb "
            "does rather than what a capability decides"
        )


def test_every_staged_authoring_request_reaches_the_analysis(
    commit_message_md: str,
) -> None:
    """Review caught the mode table contradicting the claim beneath it.

    A conversational "write a commit message" on a staged tree routed straight
    to WRITE, so the partition analysis ran or did not run depending on how the
    user phrased the ask — while the paragraph below the table and the worked
    example both said it runs on every commit. The surface decides whether the
    result is applied, never whether the question gets asked.
    """
    modes = _section(commit_message_md, "## Mode detection")
    row = next((r for r in _rows(modes) if "write/draft a commit" in r), None)
    assert row, "the mode table no longer routes the conversational authoring ask"
    assert "**SPLIT**" in row, (
        "a staged authoring request routes past the partition analysis, making it "
        f"conditional on phrasing: {row!r}"
    )
    assert "decides only whether the result is applied" in modes, (
        "the table does not state that the surface governs application rather "
        "than whether the analysis runs"
    )


def test_writes_never_commit_rule_is_scoped_to_its_workflow(
    commit_message_md: str,
) -> None:
    """WRITE forbade outright what the applying verb exists to do.

    SPLIT's N=1 case is WRITE, so an unqualified "never run git commit directly"
    in WRITE's output contract makes the verb proposal-only for the single-concern
    tree — the commonest case there is. The rule is right for the workflow and
    wrong as an absolute; execution is the invocation layer's call.
    """
    write = _section(commit_message_md, "## WRITE mode workflow")
    line = next((ln for ln in write.splitlines() if "Never run `git commit` directly" in ln), None)
    assert line, "WRITE no longer states where committing is decided"
    assert "from this workflow" in line, (
        f"WRITE's prohibition is unqualified, so SPLIT's N=1 case cannot apply: {line!r}"
    )


def test_curation_reads_the_worktree_column_not_a_code_list(split_mode: str) -> None:
    """Enumerating two porcelain codes misses most of the states that matter.

    ` M` and `MM` are two of many ways tracked work is left behind: an unstaged
    deletion, a typechange, a rename-then-edit all say the same thing and none
    matched, so those trees read as fully staged and reached the automatic path
    against an index the user had curated by hand.
    """
    body = split_mode.split("### 2. The curation rule", 1)[1].split("### 3.", 1)[0]
    assert "worktree column" in body, (
        "curation is detected from a list of status codes rather than from the "
        "column that carries the answer, so the list decides what is missed"
    )
    assert "non-space" in body, (
        "the rule does not say which column values count, leaving the code list "
        "as the operative definition after all"
    )


def test_the_secret_veto_claims_only_what_its_catalog_covers(split_mode: str) -> None:
    """A veto that cannot fire reads exactly like one that can.

    The row promised to match a secret in a staged hunk, and the catalog it cites
    excludes diff content by design. The contract test that checked the citation
    could not see this: the file existed and the anchor was there, and the row
    still described a scan nothing performs.
    """
    table = split_mode.split("### 8. Guard vetoes", 1)[1].split("###", 1)[0]
    row = next((r for r in _rows(table) if "secret" in r.split("|")[1].lower()), None)
    assert row, "the veto table has no secret row"
    assert "staged hunk" not in row, (
        f"the veto claims a scan of staged content its catalog excludes: {row!r}"
    )
    body = split_mode.split("### 8. Guard vetoes", 1)[1].split("###", 1)[0]
    assert "publishes nothing" in body, (
        "the exclusion of staged content is unexplained, so the next reader "
        "restores the unsupported veto as an oversight fix"
    )


def test_the_apply_protocol_rebuilds_the_index_per_partition(split_mode: str) -> None:
    """`git add -- <paths>` against a fully staged index is a no-op.

    Reproduced before the fix: the first commit took all three partitions. The
    input is already staged, so isolating a partition means rebuilding the index
    from a snapshot of what the user staged — and from the snapshot rather than
    the worktree, or a partially-staged file contributes hunks the user withheld.
    """
    body = split_mode.split("### 9. Output", 1)[1]
    # The executable fence, not the section: the paragraph under it explains why
    # `git restore --staged --source=` is load-bearing, so a whole-section search
    # stays green while the commands themselves regress to `git add`. Mutation
    # found exactly that.
    recipe = re.search(r"```bash\n(.*?)```", body, re.DOTALL)
    assert recipe, "the apply protocol is no longer an executable bash fence"
    commands = recipe.group(1)
    assert "git write-tree" in commands, (
        "the apply protocol does not snapshot the index, so partition staging "
        "cannot be isolated from the rest of the pile"
    )
    assert "restore --staged" in commands and "--source=" in commands, (
        "partitions are staged from the working tree rather than from the "
        "snapshot, which absorbs hunks the user deliberately left unstaged"
    )
    assert "git add" not in commands, (
        "the protocol stages with `git add` against an already-staged index, "
        "which is a no-op — the first commit then takes every partition"
    )
    assert "git read-tree" in body, (
        "no recovery path restores the original index after a partial failure"
    )


def test_an_unstageable_partition_stops_the_whole_series(split_mode: str) -> None:
    """The edge case contradicted the anti-pattern three sections below it.

    Applying every partition that can be staged non-interactively and leaving the
    intra-file one as a proposal builds precisely the partial series the veto rule
    refuses: some of an ordered series in history, no message describing that
    state, and an undo recipe whose count is wrong.
    """
    edge = split_mode.split("### SPLIT edge cases", 1)[1]
    entry = next((p for p in edge.split("\n- ") if "intra-file" in p), None)
    assert entry, "the intra-file edge case is gone"
    assert "whole invocation" in entry, (
        f"an unstageable partition degrades alone, building a partial series: {entry!r}"
    )


def test_only_implemented_verbs_are_advertised(router: str) -> None:
    """The grammar promised an API that dispatches nowhere.

    The polarity table names `pr`, `merge`, and `release` so a future verb
    inherits a safe default rather than re-deriving it — worth keeping — but
    nothing said they are unimplemented, so `/git-toolkit pr --apply` read as
    accepted-but-undefined rather than refused.
    """
    arguments = _section(router, "## Arguments")
    assert "only verb implemented today" in arguments, (
        "the grammar does not say which verbs exist, so an unimplemented one "
        "reads as accepted"
    )
    assert "refused by name" in arguments, (
        "an unimplemented verb has no stated handling, which leaves guessing as "
        "the default behaviour"
    )


def test_the_working_tree_branch_swaps_its_inputs(split_mode: str) -> None:
    """The branch existed because the index is empty, and then read the index.

    Step 1's four reads are all `--cached`, which return nothing on exactly the
    tree this branch handles — so the steps below would run against an empty
    pile and report a clean tree. Untracked files need naming separately because
    no form of `git diff` shows them at all.
    """
    body = split_mode.split("### 1. Read the pile", 1)[1].split("### 2.", 1)[0]
    assert "git diff HEAD --numstat" in body, (
        "the working-tree branch does not replace the cached reads, so it "
        "partitions an empty pile"
    )
    assert "git ls-files --others --exclude-standard" in body, (
        "untracked files are never listed, and no git diff form reveals them"
    )
    assert "read each listed file's contents" in body, (
        "the untracked read stops at names, which cannot be grouped by concern "
        "or written into a message"
    )
    assert "guard them on whether the branch has a commit yet" in body, (
        "the HEAD-relative reads are unguarded, so this branch fails on the "
        "repository-before-its-first-commit case it also serves"
    )


def test_unmeasurable_churn_does_not_clear_the_floor(split_mode: str) -> None:
    """`--numstat` does not always yield a number.

    A binary file reports `-`, a pure rename reports `0`, and a rename-only pile
    totals zero — so the 60% dominance clause has no denominator. Left undefined
    it reads as satisfied, which is the same failure the unknown co-change rate
    had: a veto cleared by an unevaluable clause.
    """
    body = split_mode.split("### 1. Read the pile", 1)[1].split("### 2.", 1)[0]
    assert "Unknown or zero total churn leaves the dominance clause unmet" in body, (
        "a pile with no measurable churn has no defined tier, so the applying "
        "verb behaves differently on a rename-only pile than on any other"
    )


def test_the_force_push_veto_says_how_to_detect_its_state(split_mode: str) -> None:
    """A veto whose trigger cannot be observed never fires.

    A fresh invocation has no memory of the reset that produced its pile: the
    index and status alone do not say whether the unwound commit was pushed, and
    the impact reference's recipes need the removed SHA, which nothing recovers.
    """
    table = split_mode.split("### 8. Guard vetoes", 1)[1].split("###", 1)[0]
    row = next((r for r in _rows(table) if "force-push" in r.split("|")[1].lower()), None)
    assert row, "the veto table has no force-push row"
    assert "git reflog" in row, (
        "the veto does not recover the commit that was unwound, so the impact "
        f"detection it defers to has no input: {row!r}"
    )
    assert "--contains" in row, (
        f"nothing establishes whether a remote still holds that commit: {row!r}"
    )


def test_the_apply_protocol_survives_an_unborn_branch(split_mode: str) -> None:
    """The initial commit is a path through here now, not an exotic case.

    Routing every staged authoring request through SPLIT put the first commit of
    a repository on this protocol, and a bare `git rev-parse HEAD` fails on an
    unborn branch — before any partition is committed. Recovery differs too:
    there is no commit to reset back to, only a ref to delete.
    """
    body = split_mode.split("### 9. Output", 1)[1]
    recipe = re.search(r"```bash\n(.*?)```", body, re.DOTALL)
    assert recipe, "the apply protocol is no longer an executable bash fence"
    assert "rev-parse --verify -q HEAD" in recipe.group(1), (
        "the protocol takes HEAD unguarded, so it dies on a repository with no "
        "commits rather than creating its first one"
    )
    # Both homes, because they do different jobs and the example alone survived
    # deleting the explanation when this checked the section as a whole.
    assert "there is no commit to return to" in body, (
        "the protocol does not explain why an unborn branch recovers differently, "
        "so the command in the template reads as an alternative rather than the "
        "only thing that works"
    )
    template = body.split("```", 2)[2] if body.count("```") > 2 else body
    assert "git update-ref -d HEAD" in template, (
        "the output template omits the unborn recovery, so a reader copying it "
        "after a failed first commit has no way back"
    )
    assert "git read-tree --empty" not in recipe.group(1), (
        "the recipe clears the index to nothing rather than to HEAD, which stages "
        "every unrestored path as a deletion — the first commit of a parented "
        "series then removes the rest of the tree"
    )


def test_the_output_shows_the_reversal(split_mode: str) -> None:
    """Reversibility claimed is reversibility shown.

    The apply default rests on the series being one command away from undone,
    so the command has to be in the output rather than in the reader's head.
    """
    section = split_mode.split("### 9. Output", 1)
    assert len(section) == 2, "SPLIT mode has no output section"
    body = section[1]
    assert "git reset --soft HEAD~" in body, (
        "the output template does not carry the undo recipe the apply default "
        "is justified by"
    )
    # Both reversals, because `HEAD~N` cannot resolve for a series that began on
    # an unborn branch — the successful path, not only the failure path.
    assert "git update-ref -d HEAD" in body, (
        "only the parented reversal is offered, so the advertised undo fails "
        "after a series that created a repository's first commits"
    )
    assert "had no commit before this series" in body, (
        "the template does not say which reversal applies when, leaving a reader "
        "to pick between two commands on their own"
    )
    assert "--dry-run" in body, "the output template does not surface the rehearsal path"
