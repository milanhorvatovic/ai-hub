"""Holds the fleet's context cost against a committed baseline.

The numbers themselves are reported, not gated — how much a skill may grow is a
judgment nobody has data for yet. What blocks is the baseline going stale: a PR
that changes a skill's cost and leaves the recorded figure alone would make
every later delta a comparison against a fossil, which is the failure this whole
measurement exists to end. The same split the description corpora use, where the
evaluator's precision and recall scores are advisory and the corpus-hash
freshness check blocks.

So a failure here is not "the skill got too big". It is "the recorded cost no
longer describes the tree", and the fix is to refresh and review the diff.

One drift is tolerated by design: release-please rewriting the annotated
`metadata.version` on the release branch, which the record absorbs by carrying
the version its numbers were measured at — the support module states the why.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests.support.context_cost import (
    _DECLARED_BINARY_SUFFIXES,
    drift,
    frontmatter_bytes,
    lf_bytes,
    measure,
    record_for,
    skill_version,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
SKILLS_ROOT = REPO_ROOT / "skills"
BASELINE_PATH = REPO_ROOT / "tests" / "skills" / "context-cost-baseline.json"

REFRESH = "./venv/bin/python -m tests.support.context_cost"

SKILL_NAMES = sorted(path.parent.name for path in SKILLS_ROOT.glob("*/SKILL.md"))


@pytest.fixture(scope="module")
def baseline() -> dict[str, dict[str, int | str]]:
    return json.loads(BASELINE_PATH.read_text(encoding="utf-8"))


def test_baseline_covers_exactly_the_shipped_skills(baseline) -> None:
    assert sorted(baseline) == SKILL_NAMES, (
        f"baseline and skills/ disagree on which skills exist; refresh with {REFRESH}"
    )


@pytest.mark.parametrize("name", SKILL_NAMES)
def test_recorded_cost_still_describes_the_tree(name: str, baseline) -> None:
    recorded = baseline.get(name)
    assert recorded is not None, f"{name} has no recorded cost; refresh with {REFRESH}"

    unexplained = drift(recorded, record_for(SKILLS_ROOT / name))
    assert not unexplained, (
        f"{name}'s recorded context cost is stale: {unexplained}\n"
        f"Refresh with {REFRESH}, then review the deltas in the diff — that "
        "review is the point of the number."
    )


def _router_at(version: str, body: bytes = b"Body.\n") -> bytes:
    return (
        b'---\nname: sample\nmetadata:\n  version: "'
        + version.encode("ascii")
        + b'" # x-release-please-version\n---\n\n'
        + body
    )


@pytest.mark.parametrize(
    ("before", "after"), [("1.9.0", "1.10.0"), ("1.9.9", "2.0.0")], ids=["wider", "same-width"]
)
def test_a_release_bump_alone_is_not_drift(tmp_path: Path, before: str, after: str) -> None:
    """The one tolerated drift, because nothing on the release PR can refresh.

    release-please rewrites the annotated version on a branch that must merge
    unmodified, so a width-crossing bump moves discovery, router, and load by
    the width change and the record has no way to follow. Restating the record
    at the measured version absorbs exactly that shift.
    """
    skill = tmp_path / "sample"
    skill.mkdir()
    (skill / "SKILL.md").write_bytes(_router_at(before))
    recorded = record_for(skill)

    (skill / "SKILL.md").write_bytes(_router_at(after))
    measured = record_for(skill)
    shift = len(after) - len(before)
    assert measured["skill_md_bytes"] == recorded["skill_md_bytes"] + shift
    assert measured["discovery_bytes"] == recorded["discovery_bytes"] + shift
    assert drift(recorded, measured) == {}


def test_a_bump_with_any_other_edit_is_still_drift(tmp_path: Path) -> None:
    """The tolerance is the bump's arithmetic, not a small-change allowance.

    An edit landing beside the bump moves the router without moving discovery,
    which no version width can explain — the guard still demands a refresh.
    """
    skill = tmp_path / "sample"
    skill.mkdir()
    (skill / "SKILL.md").write_bytes(_router_at("1.9.0"))
    recorded = record_for(skill)

    (skill / "SKILL.md").write_bytes(_router_at("1.10.0", body=b"Body, grown.\n"))
    assert drift(recorded, record_for(skill))


def test_a_record_without_a_version_reads_as_ordinary_staleness(tmp_path: Path) -> None:
    """The transition case: a branch carrying the old baseline schema meets
    this guard, and the answer must be the refresh message, not a KeyError."""
    skill = tmp_path / "sample"
    skill.mkdir()
    (skill / "SKILL.md").write_bytes(_router_at("1.0.0"))
    versionless = {k: v for k, v in record_for(skill).items() if k != "version"}

    assert list(drift(versionless, record_for(skill))) == ["version"]


def test_the_version_is_read_from_the_frontmatter_not_the_prose(tmp_path: Path) -> None:
    """A router quoting the annotated line in a worked example must not stand
    in for the real one. The annotation lives in the frontmatter or nowhere: a
    whole-file search would adopt the quoted sample — recording a version
    nothing releases — exactly when the real annotation is missing."""
    skill = tmp_path / "sample"
    skill.mkdir()
    quoted = b'```yaml\nmetadata:\n  version: "9.9.9" # x-release-please-version\n```\n'
    (skill / "SKILL.md").write_bytes(b"---\nname: sample\n---\n\n" + quoted)

    with pytest.raises(ValueError, match="annotated metadata.version"):
        skill_version(skill)


def test_a_router_without_the_annotation_cannot_be_recorded(tmp_path: Path) -> None:
    """Fail loud: a version the refresher guessed at would make every later
    restatement wrong, so the absence is an error and not a default."""
    skill = tmp_path / "sample"
    skill.mkdir()
    (skill / "SKILL.md").write_bytes(b"---\nname: sample\n---\n\nBody.\n")

    with pytest.raises(ValueError, match="annotated metadata.version"):
        record_for(skill)


@pytest.mark.parametrize(
    "document", ["AGENTS.md", "CONTRIBUTING.md", "docs/adding-a-skill.md"], ids=lambda p: Path(p).name
)
def test_the_contributor_docs_name_the_refresh_command(document: str) -> None:
    """A gate nobody declared is a gate contributors meet as a CI failure.

    Adding a skill now fails this suite until the baseline records it, which is
    a wiring step like the manifest and the corpus — so all three declaration
    surfaces name the command the failure message names. Pinned because they
    drift apart silently: the gate keeps working while the docs stop describing
    it.
    """
    text = (REPO_ROOT / document).read_text(encoding="utf-8")

    assert BASELINE_PATH.name in text
    assert REFRESH.removeprefix("./") in text


def test_the_runbook_lists_the_baseline_as_a_wiring_step() -> None:
    """In the checklist, not only in the prose below it.

    Someone adding a skill reads the table and works down it; a step that exists
    only in a later section is a step they meet as a failing test. Asserting the
    filename appears somewhere in the document does not catch that — the section
    alone satisfies it — so this looks for the row.
    """
    runbook = (REPO_ROOT / "docs" / "adding-a-skill.md").read_text(encoding="utf-8")
    rows = [line for line in runbook.splitlines() if line.startswith("|")]

    listed = [
        row for row in rows if BASELINE_PATH.name in row and "test_context_cost.py" in row
    ]
    assert listed, "the wiring checklist has no row for the context-cost baseline"


def test_counts_ignore_the_line_endings_the_checkout_chose(tmp_path: Path) -> None:
    """A CRLF checkout must report what an LF checkout reports.

    `.gitattributes` checks markdown out native, so the Windows legs of the
    matrix read every file a byte per line heavier. Raw counts would make the
    platform the largest mover in the trend, so the guard is here rather than in
    a comment on the normalization.

    Every fixture in this module writes bytes rather than text: `write_text`
    translates `\n` to `\r\n` on Windows, so a "LF" fixture built that way is
    already CRLF there and converting it again yields `\r\r\n`. That corrupts
    the frontmatter delimiter and fails this test for a reason that has nothing
    to do with the code under it — which is exactly what it did on the first CI
    run. A suite about byte counts cannot let the platform choose its input.
    """
    skill = tmp_path / "sample"
    (skill / "references").mkdir(parents=True)
    (skill / "SKILL.md").write_bytes(
        b"---\nname: sample\ndescription: one\n---\n\nSee `references/one.md`.\n"
    )
    (skill / "references" / "one.md").write_bytes(b"# One\n\nBody line.\n")

    as_lf = measure(skill)
    for path in sorted(skill.rglob("*.md")):
        path.write_bytes(path.read_bytes().replace(b"\n", b"\r\n"))

    assert measure(skill) == as_lf


@pytest.mark.parametrize(
    ("label", "content", "expected"),
    [
        ("normal block", b"---\nname: x\n---\n\nBody.\n", 16),
        ("block closing at end of file", b"---\nname: x\n---", 15),
        ("thematic break, no frontmatter", b"---\n\n# Title\n\n----\n\nBody.\n", 0),
        ("value line opening with the delimiter", b"---\nname: x\n---note: y\n---\n\nB\n", 27),
        ("never closed", b"---\nname: x\n\nBody.\n", 0),
    ],
    ids=lambda value: value if isinstance(value, str) else "",
)
def test_the_closing_delimiter_is_a_line_not_a_prefix(
    tmp_path: Path, label: str, content: bytes, expected: int
) -> None:
    """A line that *is* `---`, not one that starts with it.

    Scanning for the prefix ends the block early on a value like `---note: y`,
    and invents a block in a file that merely opens with a thematic break and
    closes with `----` further down — billing prose as discovery metadata.
    """
    path = tmp_path / "x.md"
    path.write_bytes(content)

    assert frontmatter_bytes(path) == expected


def test_a_reference_with_frontmatter_is_load_cost_not_discovery_cost(tmp_path: Path) -> None:
    """Discovery is what a harness reads before it routes anywhere.

    A reference is opened after routing, so frontmatter on one is a load cost.
    Billing every markdown file with a block would inflate discovery the day a
    reference grows one — latent, since none carries frontmatter today, and the
    reason the contributor set is enumerated rather than globbed.
    """
    skill = tmp_path / "sample"
    (skill / "references").mkdir(parents=True)
    (skill / "SKILL.md").write_bytes(b"---\nname: sample\n---\n\nSee `references/one.md`.\n")
    reference = skill / "references" / "one.md"
    reference.write_bytes(b"---\nname: one\n---\n\nBody.\n")

    cost = measure(skill)
    assert frontmatter_bytes(reference) > 0
    assert cost.discovery_bytes == frontmatter_bytes(skill / "SKILL.md")
    assert cost.load_bytes == cost.skill_md_bytes + lf_bytes(reference)


def test_a_reference_nested_under_a_reserved_name_is_still_billed(tmp_path: Path) -> None:
    """`assets` and `scripts` are reserved at a skill's top level, not anywhere.

    Testing every path component excludes `references/scripts/guide.md`, which
    is a reference that happens to sit in a directory sharing the name — loaded
    like any other and billed like any other. Latent: no skill nests one today.
    """
    skill = tmp_path / "sample"
    (skill / "references" / "scripts").mkdir(parents=True)
    (skill / "SKILL.md").write_bytes(
        b"---\nname: sample\n---\n\nSee `references/scripts/guide.md`.\n"
    )
    nested = skill / "references" / "scripts" / "guide.md"
    nested.write_bytes(b"# Guide\n")

    cost = measure(skill)
    assert cost.files == 2
    assert cost.load_bytes == cost.skill_md_bytes + lf_bytes(nested)


def test_a_reached_binary_keeps_every_byte_it_has(tmp_path: Path) -> None:
    """Normalization is for line endings, and a binary has none.

    The markdown-link collector accepts any relative target, so an image or a
    PDF can be reached. Rewriting `\\r\\n` inside one would report it smaller
    than it loads, by however many of those pairs its payload happens to hold —
    silently, since nothing else would disagree. Latent: nothing links a binary
    today, which is why the case is stated rather than waited for.
    """
    skill = tmp_path / "sample"
    (skill / "references").mkdir(parents=True)
    (skill / "SKILL.md").write_bytes(b"---\nname: sample\n---\n\nSee [chart](references/c.png).\n")
    binary = skill / "references" / "c.png"
    # A real PNG header: the signature's own CRLF, then an IHDR length whose
    # NUL bytes are what marks the blob binary to git and to this code.
    binary.write_bytes(b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\r\n")

    cost = measure(skill)
    assert lf_bytes(binary) == len(binary.read_bytes())
    assert cost.load_bytes == cost.skill_md_bytes + len(binary.read_bytes())


def test_a_declared_binary_without_a_nul_byte_is_still_raw(tmp_path: Path) -> None:
    """The attribute decides, not the content.

    `.gitattributes` marks `.jpg` binary, which is `-text`: git never normalizes
    it however it looks inside. A small JPEG can carry no NUL byte at all, so a
    content sniff on its own would rewrite `\r\n` pairs that are payload and
    report the file shorter than it loads.
    """
    skill = tmp_path / "sample"
    (skill / "references").mkdir(parents=True)
    (skill / "SKILL.md").write_bytes(b"---\nname: sample\n---\n\nSee [p](references/p.jpg).\n")
    photo = skill / "references" / "p.jpg"
    photo.write_bytes(b"\xff\xd8\xff\xe0JFIF\r\n\r\ntrailer\xff\xd9")
    assert b"\x00" not in photo.read_bytes()

    assert lf_bytes(photo) == len(photo.read_bytes())
    assert measure(skill).load_bytes == measure(skill).skill_md_bytes + len(photo.read_bytes())


def test_an_uppercase_suffix_follows_the_attributes_not_the_intent(tmp_path: Path) -> None:
    """`*.png` does not match `P.PNG`, and neither should this.

    Attribute patterns are matched with case on a case-sensitive checkout —
    `git check-attr` reports `IMAGE.PNG` as `text: auto`, not binary — so git
    may deliver it CRLF on Windows. Counting it raw because the suffix looks
    like an image would make the recorded number depend on the platform, which
    is the one property this measurement has to keep.
    """
    skill = tmp_path / "sample"
    (skill / "references").mkdir(parents=True)
    (skill / "SKILL.md").write_bytes(b"---\nname: sample\n---\n\nSee [p](references/P.PNG).\n")
    shouty = skill / "references" / "P.PNG"
    shouty.write_bytes(b"header\r\nbody\r\n")

    assert lf_bytes(shouty) == len(b"header\nbody\n")


def test_a_text_target_outside_any_suffix_list_is_still_normalized(tmp_path: Path) -> None:
    """Because git decides how it arrives, and git goes by content.

    `.gitattributes` sets `text=auto` repo-wide, so a linked `.csv` — or a file
    with no suffix at all — is text to git and arrives CRLF on Windows. Keying
    the split to a list of known suffixes would count it raw there and fail a
    baseline refreshed on Linux, which is the same platform trap from the other
    side.
    """
    skill = tmp_path / "sample"
    (skill / "references").mkdir(parents=True)
    (skill / "SKILL.md").write_bytes(
        b"---\nname: sample\n---\n\nSee [data](references/d.csv) and [n](references/NOTES).\n"
    )
    for name in ("d.csv", "NOTES"):
        (skill / "references" / name).write_bytes(b"a,b\r\n1,2\r\n")

    cost = measure(skill)
    assert lf_bytes(skill / "references" / "d.csv") == len(b"a,b\n1,2\n")
    assert cost.load_bytes == cost.skill_md_bytes + 2 * len(b"a,b\n1,2\n")


def test_frontmatterless_files_cost_nothing_to_discover(tmp_path: Path) -> None:
    """Discovery bills frontmatter only, so a reference adds load and no more."""
    skill = tmp_path / "sample"
    (skill / "references").mkdir(parents=True)
    router = skill / "SKILL.md"
    router.write_bytes(b"---\nname: sample\n---\n\nSee `references/one.md`.\n")
    reference = skill / "references" / "one.md"
    reference.write_bytes(b"# One\n")

    cost = measure(skill)
    assert frontmatter_bytes(reference) == 0
    assert cost.discovery_bytes == frontmatter_bytes(router)
    assert cost.load_bytes == cost.skill_md_bytes + lf_bytes(reference)


def test_discovery_bills_a_capability_the_router_never_reaches(tmp_path: Path) -> None:
    """An orphaned capability costs discovery but not load.

    Whoever scans the directory reads its frontmatter whether the router points
    at it or not, so discovery has to come from the tree rather than the walk.
    Computing it from the walk gives the same answer on a valid fleet and stops
    being right the moment the orphan checks do — this is the case that
    separates the two.
    """
    skill = tmp_path / "sample"
    (skill / "capabilities" / "orphan").mkdir(parents=True)
    (skill / "SKILL.md").write_bytes(b"---\nname: sample\n---\n\nNo rows.\n")
    orphan = skill / "capabilities" / "orphan" / "capability.md"
    orphan.write_bytes(b"---\nname: orphan\n---\n\nUnrouted.\n")

    cost = measure(skill)
    assert cost.discovery_bytes == frontmatter_bytes(skill / "SKILL.md") + frontmatter_bytes(orphan)
    assert cost.files == 1
    assert cost.load_bytes == cost.skill_md_bytes


def test_a_route_through_a_payload_directory_still_reaches_what_it_links(
    tmp_path: Path,
) -> None:
    """`SKILL.md` → `assets/index.md` → `references/detail.md`, all three billed.

    Excluding a whole directory after the walk had already run left a shape
    where a file was dropped while everything it linked stayed — billing a
    descendant reached only through something declared unreachable. Excluding
    payload rather than the directory dissolves it: the only unbilled files are
    non-markdown, and the walk never traverses those, so nothing can be reached
    exclusively through one. Pinned because a directory-wide exclusion would
    reintroduce the shape without failing anything else here.
    """
    skill = tmp_path / "sample"
    (skill / "assets").mkdir(parents=True)
    (skill / "references").mkdir()
    (skill / "SKILL.md").write_bytes(b"---\nname: sample\n---\n\nSee [i](assets/index.md).\n")
    (skill / "assets" / "index.md").write_bytes(b"# Index\n\nSee [d](../references/detail.md).\n")
    (skill / "references" / "detail.md").write_bytes(b"# Detail\n")
    (skill / "assets" / "tool.json").write_bytes(b"{}\n")

    cost = measure(skill)
    assert cost.files == 3
    assert cost.load_bytes == sum(
        len((skill / name).read_bytes())
        for name in ("SKILL.md", "assets/index.md", "references/detail.md")
    )


def test_payload_is_not_billed_but_documentation_beside_it_is(tmp_path: Path) -> None:
    """`assets/` and `scripts/` hold payload, and payload is not context.

    A config handed to a formatter and a script that gets run are not read by
    anyone; the bytes belong to the tool. Documentation that happens to live
    beside them is a different thing — docs-steward's router names
    `assets/configs/README.md` in the same sentence as its references, and that
    file is prose about the configs rather than one of them. Excluding the whole
    directory undercounts the skill by the size of that document.
    """
    skill = tmp_path / "sample"
    (skill / "assets").mkdir(parents=True)
    (skill / "SKILL.md").write_bytes(
        b"---\nname: sample\n---\n\nPolicy: [a](assets/policy.md). Config: `assets/tool.json`.\n"
    )
    policy = skill / "assets" / "policy.md"
    policy.write_bytes(b"# Policy\n\nWhy these settings.\n")
    (skill / "assets" / "tool.json").write_bytes(b'{"rule": true}\n')

    cost = measure(skill)
    assert cost.files == 2
    assert cost.load_bytes == cost.skill_md_bytes + lf_bytes(policy)


def test_the_declared_binary_suffixes_match_the_attributes_file() -> None:
    """The code's list and `.gitattributes` are one decision in two places.

    `binary` is `-text`: git never normalizes those files whatever they contain,
    so the content heuristic must not get a vote on them. Keeping the set in
    Python means it can drift from the attributes file that motivates it, and
    the drift is invisible — a suffix dropped here still passes every count on a
    fleet that ships no binaries.
    """
    attributes = (REPO_ROOT / ".gitattributes").read_text(encoding="utf-8")
    declared = {
        line.split()[0].removeprefix("*")
        for line in attributes.splitlines()
        if line.strip().endswith(" binary")
    }

    assert declared == set(_DECLARED_BINARY_SUFFIXES), (
        "the binary suffixes in .gitattributes and context_cost.py disagree"
    )
