"""One structural suite for every skill under skills/.

Every skill must satisfy the same structural invariants — frontmatter shape,
Agent-Skills spec limits, annotated semver, router/capability registration
consistency, and internal-link resolution. Parametrizing over the discovered
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

_CAPABILITY_PATH = re.compile(r"capabilities/([a-z0-9-]+)/capability\.md")

# Extensions checked by the backtick-path collector. Directory mentions and
# glob patterns never match (no trailing extension / `*` outside the class).
_CHECKED_EXTENSIONS = r"(?:md|json|ndjson|py|yaml|yml|toml|sh)"

# A backtick token containing `/` is treated as a skill-internal pointer when
# its first segment is a `../` traversal or a skill-content directory. Other
# first segments (`docs/`, `.github/`, `tests/`, …) are external repo paths
# that appear as *data* in skill prose (e.g. the oss conventions catalog).
_INTERNAL_FIRST_SEGMENTS = frozenset({"..", "references", "capabilities", "scripts", "assets"})

_BACKTICK_TOKEN = re.compile(rf"`([A-Za-z0-9_./-]+\.{_CHECKED_EXTENSIONS})`")

# Relative markdown-link targets; external schemes and absolute paths are
# filtered by the collector, anchors are stripped by the pattern.
_MARKDOWN_LINK = re.compile(r"\]\(([^)#\s]+)(?:#[^)\s]*)?\)")

_FENCE = re.compile(r"^\s{0,3}(`{3,}|~{3,})")

# (check, skill-name) -> reason. Strict xfail: proof the suite detects the
# defect today, and a forced cleanup of this table by the PR that fixes it.
KNOWN_FAILURES: dict[tuple[str, str], str] = {
    ("description_limit", "oss-repository-conventions"): (
        "S1 skills-spec-compliance-sweep: description is 1058 chars, spec max 1024"
    ),
    ("backtick_paths", "docs-steward"): (
        "S1 skills-spec-compliance-sweep: skill-root-relative backtick paths in "
        "nested files resolve from the wrong base (audit docs-steward finding 6)"
    ),
    ("cross_capability", "git-toolkit"): (
        "G1 shared-reference-lift: capabilities link sibling capabilities; G1 "
        "moves the shared material into references/ and kills sibling links"
    ),
    ("markdown_links", "oss-repository-conventions"): (
        "O3 scaffold-template-convention: unfenced scaffold templates carry "
        "target-repo links (LICENSE-APACHE, SECURITY.md, …); O3's fenced-block "
        "convention turns template content into skippable data"
    ),
}


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
    return set(_CAPABILITY_PATH.findall((skill / "SKILL.md").read_text(encoding="utf-8")))


def _capabilities_on_disk(skill: Path) -> set[str]:
    cap_dir = skill / "capabilities"
    if not cap_dir.is_dir():
        return set()
    return {p.name for p in cap_dir.iterdir() if (p / "capability.md").is_file()}


def _prose_lines(md_file: Path):
    """Yield (lineno, line) for lines outside fenced code blocks — fenced
    content is data (worked examples, scaffold templates), not skill
    navigation, so its link-shaped text is never a pointer."""
    fence_char: str | None = None
    for lineno, line in enumerate(md_file.read_text(encoding="utf-8").splitlines(), start=1):
        if m := _FENCE.match(line):
            marker_char = m.group(1)[0]
            if fence_char is None:
                fence_char = marker_char
            elif marker_char == fence_char:
                fence_char = None
            continue
        if fence_char is None:
            yield lineno, line


def _backtick_paths(md_file: Path) -> list[tuple[str, int]]:
    """(token, 1-based line) for every backtick-quoted skill-internal path.

    Only `/`-bearing tokens whose first segment is a `../` traversal or a
    skill-content directory are pointers; bare filenames and external repo
    paths are prose mentions. Resolution is file-relative (the foundry rule
    and the house convention from git-toolkit's reference tests).
    """
    out: list[tuple[str, int]] = []
    for lineno, line in _prose_lines(md_file):
        for m in _BACKTICK_TOKEN.finditer(line):
            token = m.group(1)
            if "/" in token and token.split("/", 1)[0] in _INTERNAL_FIRST_SEGMENTS:
                out.append((token, lineno))
    return out


def _markdown_links(md_file: Path) -> list[tuple[str, int]]:
    """(target, 1-based line) for every relative markdown-link target."""
    out: list[tuple[str, int]] = []
    for lineno, line in _prose_lines(md_file):
        for m in _MARKDOWN_LINK.finditer(line):
            target = m.group(1)
            if "://" in target or target.startswith(("mailto:", "/")):
                continue
            out.append((target, lineno))
    return out


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
def test_markdown_links_resolve(skill: Path) -> None:
    _resolve_all(skill, _markdown_links, "markdown links", target_must_be_file=False)


@pytest.mark.parametrize("skill", skill_params("backtick_paths"))
def test_backtick_paths_resolve(skill: Path) -> None:
    _resolve_all(skill, _backtick_paths, "backtick path pointers")


@pytest.mark.parametrize("skill", skill_params("cross_capability"))
def test_no_cross_capability_references(skill: Path) -> None:
    """A file under capabilities/<a>/ must not point into capabilities/<b>/ —
    capabilities load independently, so a sibling link hauls a second
    capability along or silently degrades."""
    cap_root = (skill / "capabilities").resolve()
    offenders: list[str] = []
    for md_file in sorted(skill.glob("capabilities/**/*.md")):
        own = md_file.resolve().relative_to(cap_root).parts[0]
        for token, lineno in _backtick_paths(md_file) + _markdown_links(md_file):
            target = (md_file.parent / token).resolve()
            if not target.is_relative_to(cap_root):
                continue
            if target.relative_to(cap_root).parts[0] != own:
                offenders.append(
                    f"{md_file.relative_to(skill)}:{lineno} -> {token}"
                )
    assert not offenders, "cross-capability references:\n" + "\n".join(offenders)
