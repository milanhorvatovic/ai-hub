"""One structural suite for every skill under skills/.

Every skill must satisfy the same structural invariants — frontmatter shape,
Agent-Skills spec limits, annotated semver, router/capability registration
consistency, internal-link resolution, and the direction pointers may run
(no capability into a sibling, no shared reference into a capability), and that
every shared reference is reachable from the router. Parametrizing over the discovered
skill set means a newly added skill is validated from its first commit with no
bespoke test directory, and deleting a per-skill test directory leaves the
skill structurally covered. Per-skill *content* contracts (mantra counts,
NDJSON schemas, capability skeletons) stay in `tests/skills/<name>/`.

Skills are discovered from the working tree (`skills/*/SKILL.md`) rather than
`git ls-files`, deliberately: a work-in-progress skill gets validated before it
is ever tracked. Release wiring (config/manifest coverage) stays tracked-file
based in `tests/release/test_manifest_sync.py`.

Known-bad content that predates this suite is marked strict-xfail in
`KNOWN_FAILURES`, keyed by (check, skill), with the owning workstream in the
reason. When the owning PR fixes the content, the strict xfail flips the test
to XPASS-failure, forcing that PR to drop the entry — the mark cannot outlive
the defect.
"""

from __future__ import annotations

import re
import warnings
from pathlib import Path

import pytest

from tests.support.reachability import (
    CAPABILITY_PATH,
    backtick_paths,
    markdown_links,
    prose_lines,
    reachable_markdown,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
SKILLS_ROOT = REPO_ROOT / "skills"

# Agent-Skills spec limits for frontmatter fields.
MAX_NAME_LENGTH = 64
MAX_DESCRIPTION_LENGTH = 1024
ADVISORY_DESCRIPTION_LENGTH = 800

_SKILL_NAME = re.compile(r"[a-z0-9]+(-[a-z0-9]+)*")

# Space-separated tool names are the current house form for `allowed-tools`
# (decision point 1 of the skills-improvement plan may settle a different
# separator fleet-wide; update this pattern with it).
_ALLOWED_TOOLS = re.compile(r"[A-Za-z][A-Za-z-]*( [A-Za-z][A-Za-z-]*)*")

# `metadata.version` must be semver AND carry the x-release-please-version
# annotation — without it, release-please bumps the manifest but not SKILL.md,
# and the drift surfaces only as a confusing failure on the bot's release PR.
_ANNOTATED_SEMVER = re.compile(
    r'^\s+version:\s*"\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?"'
    r"\s*#\s*x-release-please-version\s*$",
    flags=re.MULTILINE,
)


# (check, skill-name) -> reason. Strict xfail: proof the suite detects the
# defect today, and a forced cleanup of this table by the PR that fixes it.
KNOWN_FAILURES: dict[tuple[str, str], str] = {}


def discover_skills() -> list[Path]:
    skills = sorted(p.parent for p in SKILLS_ROOT.glob("*/SKILL.md"))
    assert skills, f"no skills discovered under {SKILLS_ROOT}"
    return skills


def skill_params(check: str) -> list:
    """Per-skill pytest params for `check`, with known failures strict-xfailed."""
    params = []
    for skill in discover_skills():
        marks = []
        if reason := KNOWN_FAILURES.get((check, skill.name)):
            marks.append(pytest.mark.xfail(reason=reason, strict=True))
        params.append(pytest.param(skill, id=skill.name, marks=marks))
    return params


def parse_frontmatter(md_path: Path) -> dict[str, str]:
    """Parse a leading YAML frontmatter block into a flat dict.

    Hand-rolled because these tests run on the Python stdlib only — no PyYAML.
    Supports exactly what skill frontmatter uses: flat `key: value` pairs and
    the multi-line `>` folded scalar (descriptions). Nested mappings are NOT
    parsed — an indented child of a plain key (e.g. `metadata:` -> `version:`)
    is skipped, not turned into a sub-key; version is asserted by regex
    instead. `read_text` opens in universal-newline mode, so CRLF checkouts
    are normalized to LF before parsing.
    """
    text = md_path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        raise AssertionError(f"{md_path} missing leading frontmatter")
    end = text.find("\n---\n", 4)
    if end == -1:
        raise AssertionError(f"{md_path} frontmatter not terminated")
    body = text[4:end]

    result: dict[str, str] = {}
    current_key: str | None = None
    current_lines: list[str] = []
    for raw in body.splitlines():
        if raw.startswith("  ") and current_key is not None:
            current_lines.append(raw.strip())
            continue
        if raw.startswith("  "):
            # Nested-mapping child of a plain key; skipped on purpose (see
            # docstring).
            continue
        if current_key is not None:
            result[current_key] = " ".join(current_lines).strip()
            current_key = None
            current_lines = []
        m = re.match(r"^([a-zA-Z_-]+):\s*(.*)$", raw)
        if not m:
            continue
        key, value = m.group(1), m.group(2).strip()
        if value == ">":
            current_key = key
            current_lines = []
        elif value == "|":
            # No skill frontmatter uses a literal scalar; fail loud rather
            # than store a garbage "|" value and drop the body.
            raise AssertionError(f"{md_path}: literal-scalar (|) frontmatter is not supported")
        else:
            result[key] = value
    if current_key is not None:
        result[current_key] = " ".join(current_lines).strip()
    return result


def _routed_capabilities(skill: Path) -> set[str]:
    """Capability names routed anywhere in SKILL.md — matched over the whole
    file, not a parsed table, so multi-table routers (git-toolkit's per-phase
    tables) are unioned by construction."""
    return set(CAPABILITY_PATH.findall((skill / "SKILL.md").read_text(encoding="utf-8")))


def _capabilities_on_disk(skill: Path) -> set[str]:
    cap_dir = skill / "capabilities"
    if not cap_dir.is_dir():
        return set()
    return {p.name for p in cap_dir.iterdir() if (p / "capability.md").is_file()}


def _resolve_all(
    skill: Path, collect, description: str, target_must_be_file: bool = True
) -> None:
    """Resolve every collected pointer in every markdown file of the skill
    tree; each must exist and stay inside the tree."""
    skill_resolved = skill.resolve()
    broken: list[str] = []
    for md_file in sorted(skill.rglob("*.md")):
        for token, lineno in collect(md_file):
            target = (md_file.parent / token).resolve()
            rel = f"{md_file.relative_to(skill)}:{lineno} -> {token}"
            if not target.is_relative_to(skill_resolved):
                broken.append(f"{rel} (escapes skill tree)")
            elif not (target.is_file() if target_must_be_file else target.exists()):
                broken.append(rel)
    assert not broken, f"broken {description}:\n" + "\n".join(broken)


def testprose_lines_keep_longer_fences_closed(tmp_path: Path) -> None:
    """A ````-fenced block may embed ``` lines as content; only a same-char
    run at least as long as the opener closes it (CommonMark)."""
    md = tmp_path / "sample.md"
    md.write_text(
        "before\n"
        "````markdown\n"
        "```\n"
        "[fenced](data-not-a-link.md)\n"
        "```\n"
        "````\n"
        "after\n",
        encoding="utf-8",
    )
    assert [line for _, line in prose_lines(md)] == ["before", "after"]


@pytest.mark.parametrize("skill", skill_params("frontmatter"))
def test_frontmatter_names_the_skill(skill: Path) -> None:
    fm = parse_frontmatter(skill / "SKILL.md")
    name = fm.get("name", "")
    assert name == skill.name, f"frontmatter name {name!r} != directory {skill.name!r}"
    assert _SKILL_NAME.fullmatch(name), f"name {name!r} is not lowercase-hyphen"
    assert len(name) <= MAX_NAME_LENGTH


@pytest.mark.parametrize("skill", skill_params("description_limit"))
def test_description_within_spec_limit(skill: Path) -> None:
    description = parse_frontmatter(skill / "SKILL.md").get("description", "")
    assert description, "frontmatter missing `description`"
    if len(description) > ADVISORY_DESCRIPTION_LENGTH:
        warnings.warn(
            f"{skill.name}: description is {len(description)} chars — approaching "
            f"the {MAX_DESCRIPTION_LENGTH} spec limit",
            stacklevel=1,
        )
    assert len(description) <= MAX_DESCRIPTION_LENGTH, (
        f"description is {len(description)} chars, spec max {MAX_DESCRIPTION_LENGTH}"
    )


@pytest.mark.parametrize("skill", skill_params("version"))
def test_version_is_semver_with_release_annotation(skill: Path) -> None:
    text = (skill / "SKILL.md").read_text(encoding="utf-8")
    assert _ANNOTATED_SEMVER.search(text), (
        'metadata.version must be `version: "<semver>" # x-release-please-version` '
        "— the annotation is what lets release-please bump SKILL.md"
    )


@pytest.mark.parametrize("skill", skill_params("allowed_tools"))
def test_allowed_tools_declared_in_house_form(skill: Path) -> None:
    tools = parse_frontmatter(skill / "SKILL.md").get("allowed-tools", "")
    assert tools, "router frontmatter missing `allowed-tools`"
    assert _ALLOWED_TOOLS.fullmatch(tools), (
        f"allowed-tools {tools!r} is not space-separated tool names"
    )


@pytest.mark.parametrize("skill", skill_params("routing"))
def test_routed_capabilities_exist_on_disk(skill: Path) -> None:
    missing = _routed_capabilities(skill) - _capabilities_on_disk(skill)
    assert not missing, f"router routes to missing capabilities: {sorted(missing)}"


@pytest.mark.parametrize("skill", skill_params("routing"))
def test_no_orphan_capabilities(skill: Path) -> None:
    """A capability on disk that no router line mentions can never trigger."""
    orphans = _capabilities_on_disk(skill) - _routed_capabilities(skill)
    assert not orphans, f"capabilities on disk but not routed: {sorted(orphans)}"


@pytest.mark.parametrize("skill", skill_params("capability_frontmatter"))
def test_capabilities_declare_a_name(skill: Path) -> None:
    unnamed = [
        cap.parent.name
        for cap in sorted(skill.glob("capabilities/*/capability.md"))
        if not parse_frontmatter(cap).get("name")
    ]
    assert not unnamed, f"capabilities missing frontmatter `name`: {unnamed}"


@pytest.mark.parametrize("skill", skill_params("capability_tools"))
def test_router_tools_cover_capability_tools(skill: Path) -> None:
    """Where a capability declares allowed-tools, the router must grant at
    least those tools (router = union; a capability never needs a tool the
    router can't grant). Capabilities without the key are exempt — only oss
    and coding-principles declare per-capability tools today."""
    router_tools = set(parse_frontmatter(skill / "SKILL.md").get("allowed-tools", "").split())
    offenders: list[str] = []
    for cap in sorted(skill.glob("capabilities/*/capability.md")):
        cap_tools = set(parse_frontmatter(cap).get("allowed-tools", "").split())
        if missing := cap_tools - router_tools:
            offenders.append(f"{cap.parent.name}: {sorted(missing)}")
    assert not offenders, "capability tools the router does not grant:\n" + "\n".join(offenders)


@pytest.mark.parametrize("skill", skill_params("markdown_links"))
def testmarkdown_links_resolve(skill: Path) -> None:
    _resolve_all(skill, markdown_links, "markdown links", target_must_be_file=False)


@pytest.mark.parametrize("skill", skill_params("backtick_paths"))
def testbacktick_paths_resolve(skill: Path) -> None:
    _resolve_all(skill, backtick_paths, "backtick path pointers")


@pytest.mark.parametrize("skill", skill_params("reference_direction"))
def test_shared_references_never_point_into_capabilities(skill: Path) -> None:
    """A file under the skill-root references/ must not point into
    capabilities/ — the router and capability entry points reach down, shared
    references only sideways or up. An inversion makes the reference
    unloadable without hauling a capability along, and a pair pointing at each
    other is a cycle with no entry point. Prose names a capability instead."""
    cap_root = (skill / "capabilities").resolve()
    offenders: list[str] = []
    for md_file in sorted(skill.glob("references/**/*.md")):
        for token, lineno in backtick_paths(md_file) + markdown_links(md_file):
            if (md_file.parent / token).resolve().is_relative_to(cap_root):
                offenders.append(f"{md_file.relative_to(skill)}:{lineno} -> {token}")
    assert not offenders, "references pointing into capabilities:\n" + "\n".join(offenders)


@pytest.mark.parametrize("skill", skill_params("reference_reachability"))
def test_every_shared_reference_is_reachable(skill: Path) -> None:
    """Every skill-root reference is reachable from the router.

    A reference nothing reaches still ships and still costs bytes; it is
    simply never loaded, which is the failure that looks like nothing at all.
    The foundry validator reports it as an orphan, but no CI job runs the
    validator, so the last pointer to a file can go in an unrelated edit and
    nothing says so until someone re-runs it by hand.

    Reachability is transitive from `SKILL.md`, not "some other file mentions
    the name": two orphaned files naming each other are still orphaned, and
    the weaker check passes them. The walk's semantics are pinned on a
    synthetic tree below, because a valid fleet cannot tell a real traversal
    from a filename scan — both leave every skill green.

    The reference tree is walked recursively, matching the direction guard
    above: a nested `references/guides/setup.md` is as unloadable as a flat
    one. The same walk currently reaches every markdown file in every skill,
    not only the shared ones, so widening this beyond `references/` is a
    one-line change whenever that is wanted. A skill with no skill-root
    `references/` has nothing to reach, so the glob yields nothing and this
    passes — the right answer rather than a hole.
    """
    reachable = reachable_markdown(skill)
    unreachable = [
        ref.relative_to(skill).as_posix()
        for ref in sorted(skill.glob("references/**/*.md"))
        if ref.resolve() not in reachable
    ]
    assert not unreachable, "shared references nothing reaches:\n" + "\n".join(unreachable)


@pytest.mark.parametrize("skill", skill_params("cross_capability"))
def test_no_cross_capability_references(skill: Path) -> None:
    """A file under capabilities/<a>/ must not point into capabilities/<b>/ —
    capabilities load independently, so a sibling link hauls a second
    capability along or silently degrades."""
    cap_root = (skill / "capabilities").resolve()
    offenders: list[str] = []
    for md_file in sorted(skill.glob("capabilities/**/*.md")):
        own = md_file.resolve().relative_to(cap_root).parts[0]
        for token, lineno in backtick_paths(md_file) + markdown_links(md_file):
            target = (md_file.parent / token).resolve()
            if not target.is_relative_to(cap_root):
                continue
            if target.relative_to(cap_root).parts[0] != own:
                offenders.append(
                    f"{md_file.relative_to(skill)}:{lineno} -> {token}"
                )
    assert not offenders, "cross-capability references:\n" + "\n".join(offenders)


def test_reachability_walk_follows_pointers_not_mentions(tmp_path: Path) -> None:
    """The walk's negative cases, pinned on a synthetic tree.

    Every shipped skill is valid, so running the reachability guard against
    the fleet cannot distinguish a real traversal from one that counts any
    filename mention — a rewrite to the weaker form leaves all four skills
    green and ships. These cases fail on that rewrite instead.

    Two of them cannot be staged in the fleet at all: an unrouted capability
    is impossible there, because the orphan checks fail first. That is exactly
    why the walk takes capability edges from the router alone, and the only
    place the rule can be held to account is a tree built to break it.
    """
    skill = tmp_path / "probe-skill"
    (skill / "references" / "guides").mkdir(parents=True)
    (skill / "capabilities" / "routed").mkdir(parents=True)
    (skill / "capabilities" / "stray").mkdir(parents=True)

    # A router row is plain table text, and the fenced pointer below is a
    # backticked path a fence-blind collector would happily follow.
    (skill / "SKILL.md").write_text(
        "# Probe\n\n"
        "| routed | on demand | capabilities/routed/capability.md |\n\n"
        "```\n"
        "see `references/fenced-only.md`\n"
        "```\n",
        encoding="utf-8",
    )
    (skill / "capabilities" / "routed" / "capability.md").write_text(
        "Complements `../../references/deep.md`.\n", encoding="utf-8"
    )
    (skill / "capabilities" / "stray" / "capability.md").write_text(
        "Complements `../../references/via-stray.md`.\n", encoding="utf-8"
    )
    # Reached, and it names an unrouted capability in prose — a mention.
    (skill / "references" / "deep.md").write_text(
        "The stray one lives at capabilities/stray/capability.md.\n", encoding="utf-8"
    )
    (skill / "references" / "fenced-only.md").write_text("# Fenced only\n", encoding="utf-8")
    (skill / "references" / "via-stray.md").write_text("# Via stray\n", encoding="utf-8")
    (skill / "references" / "orphan-a.md").write_text("See `orphan-b.md`.\n", encoding="utf-8")
    (skill / "references" / "orphan-b.md").write_text("See `orphan-a.md`.\n", encoding="utf-8")
    (skill / "references" / "guides" / "nested-orphan.md").write_text("# Nested\n", encoding="utf-8")
    # An out-and-back route: reachable prose links to a repo-level document,
    # which links back in. That path exists in the repo and not in an install,
    # where only the skill directory ships.
    (skill / "references" / "deep.md").write_text(
        "The stray one lives at capabilities/stray/capability.md.\n"
        "See [the runbook](../../outside.md).\n",
        encoding="utf-8",
    )
    (tmp_path / "outside.md").write_text(
        "Back in: [policy](probe-skill/references/only-via-outside.md).\n", encoding="utf-8"
    )
    (skill / "references" / "only-via-outside.md").write_text("# Only via outside\n", encoding="utf-8")

    reached = {p.relative_to(skill.resolve()).as_posix() for p in reachable_markdown(skill)}

    assert "capabilities/routed/capability.md" in reached, "a router row is an edge"
    assert "references/deep.md" in reached, "router -> capability -> shared reference is transitive"
    assert "references/fenced-only.md" not in reached, "a pointer inside a fence is prose"
    assert "capabilities/stray/capability.md" not in reached, (
        "a capability named by a reference is a mention, not routing"
    )
    assert "references/via-stray.md" not in reached, "nothing routes through an unrouted capability"
    assert not {"references/orphan-a.md", "references/orphan-b.md"} & reached, (
        "orphans naming each other are still orphans"
    )
    assert "references/only-via-outside.md" not in reached, (
        "a route out of the skill and back does not exist once installed"
    )

    # The guard is called directly rather than re-globbed here: what needs
    # pinning is that it enumerates the reference tree recursively, and the
    # only way to state that is to let it fail on a nested orphan.
    with pytest.raises(AssertionError, match="references/guides/nested-orphan.md"):
        test_every_shared_reference_is_reachable(skill)
