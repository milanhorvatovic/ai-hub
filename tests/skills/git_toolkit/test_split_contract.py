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
    assert "--dry-run" in body, "the output template does not surface the rehearsal path"
