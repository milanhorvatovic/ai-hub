"""Aggregate per-skill release notes into the single root ``CHANGELOG.md``.

For each skill in ``.release-please-manifest.json``, find the previous per-skill
tag (``<skill>-v<x.y.z>``), read the conventional commits since that tag that
touched the skill's directory, group them into Keep-a-Changelog categories, and
emit a single CalVer-tagged section listing every skill that bumped.

If a section for the same CalVer tag already exists in ``CHANGELOG.md``, it is
replaced in place; otherwise the new section is prepended after the file's
``# Changelog`` header.

Stdlib only — fits the repo's release-scripts convention.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

# Conventional-commit type → Keep-a-Changelog category. Types absent from this
# map are dropped from the user-visible changelog (chore/ci/test/style/build).
_TYPE_TO_CATEGORY: dict[str, str] = {
    "feat": "Added",
    "fix": "Fixed",
    "perf": "Changed",
    "refactor": "Changed",
    "revert": "Changed",
    "docs": "Changed",
}

# Order categories appear in within each skill section.
_CATEGORY_ORDER: tuple[str, ...] = ("Added", "Changed", "Fixed")

_CONVENTIONAL_RE = re.compile(
    r"^(?P<type>[a-z]+)(?:\((?P<scope>[^)]+)\))?(?P<bang>!?):\s*(?P<desc>.+?)\s*$"
)


@dataclass(frozen=True)
class Commit:
    """A parsed conventional commit, stripped to what the changelog needs."""

    sha: str
    type: str
    scope: str | None
    breaking: bool
    desc: str

    @property
    def category(self) -> str | None:
        return _TYPE_TO_CATEGORY.get(self.type)


def _git(repo_root: Path, *args: str) -> str:
    """Run ``git`` and return its stdout; raises on non-zero exit."""
    return subprocess.run(
        ["git", *args],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=True,
    ).stdout


def parse_conventional(subject: str) -> Commit | None:
    """Parse a commit subject; return None for non-conventional commits."""
    match = _CONVENTIONAL_RE.match(subject.strip())
    if not match:
        return None
    return Commit(
        sha="",
        type=match.group("type"),
        scope=match.group("scope"),
        breaking=bool(match.group("bang")),
        desc=match.group("desc"),
    )


def load_manifest(repo_root: Path) -> dict[str, str]:
    """Read ``.release-please-manifest.json`` as ``{package_path: version}``."""
    return json.loads((repo_root / ".release-please-manifest.json").read_text())


def _semver_key(version: str) -> tuple[int, int, int]:
    parts = version.split(".")
    return (int(parts[0]), int(parts[1]), int(parts[2]))


def find_prev_tag(repo_root: Path, skill: str, current_version: str) -> str | None:
    """Latest ``<skill>-v<x.y.z>`` tag with a version strictly < current."""
    out = _git(repo_root, "tag", "--list", f"{skill}-v*")
    pattern = re.compile(rf"^{re.escape(skill)}-v(\d+\.\d+\.\d+)$")
    tags: list[tuple[tuple[int, int, int], str]] = []
    for raw in out.splitlines():
        tag = raw.strip()
        match = pattern.match(tag)
        if match:
            tags.append((_semver_key(match.group(1)), tag))
    if not tags:
        return None
    cur = _semver_key(current_version)
    earlier = sorted(t for t in tags if t[0] < cur)
    return earlier[-1][1] if earlier else None


def commits_since(
    repo_root: Path, skill: str, prev_tag: str | None
) -> list[Commit]:
    """Conventional commits touching ``skills/<skill>/`` since ``prev_tag``."""
    range_spec = f"{prev_tag}..HEAD" if prev_tag else "HEAD"
    out = _git(
        repo_root,
        "log",
        range_spec,
        "--no-merges",
        "--pretty=format:%H%x09%s",
        "--",
        f"skills/{skill}/",
    )
    commits: list[Commit] = []
    for line in out.splitlines():
        if not line.strip():
            continue
        sha, subject = line.split("\t", 1)
        parsed = parse_conventional(subject)
        if parsed is None:
            continue
        commits.append(
            Commit(
                sha=sha,
                type=parsed.type,
                scope=parsed.scope,
                breaking=parsed.breaking,
                desc=parsed.desc,
            )
        )
    return commits


def group_commits(commits: Iterable[Commit]) -> dict[str, list[Commit]]:
    """Group commits into Keep-a-Changelog categories in canonical order."""
    buckets: dict[str, list[Commit]] = {}
    for commit in commits:
        category = commit.category
        if category is None and not commit.breaking:
            continue
        buckets.setdefault(category or "Changed", []).append(commit)
    return {key: buckets[key] for key in _CATEGORY_ORDER if key in buckets}


def format_skill_section(
    skill: str, version: str, groups: dict[str, list[Commit]]
) -> str:
    """Markdown for one skill's ``### <skill> <version>`` block (empty if no changes)."""
    if not groups:
        return ""
    lines = [f"### {skill} {version}"]
    for category, items in groups.items():
        lines.append("")
        lines.append(f"#### {category}")
        for commit in items:
            mark = "**BREAKING:** " if commit.breaking else ""
            lines.append(f"- {mark}{commit.desc}")
    return "\n".join(lines) + "\n"


def format_calver_section(
    calver_tag: str,
    calver_date: str,
    skill_sections: list[tuple[str, str, dict[str, list[Commit]]]],
) -> str:
    """Assemble one CalVer-tagged section from the per-skill groups."""
    body = "\n".join(
        block
        for block in (format_skill_section(s, v, g) for s, v, g in skill_sections)
        if block
    )
    if not body:
        body = "_No user-visible changes._\n"
    return f"## {calver_tag} — {calver_date}\n\n{body}".rstrip() + "\n"


def rewrite_changelog(existing: str, new_section: str, calver_tag: str) -> str:
    """Replace an existing CalVer section with the same tag or prepend the new one."""
    pattern = re.compile(
        rf"^## {re.escape(calver_tag)}\b.*?(?=^## |\Z)",
        re.MULTILINE | re.DOTALL,
    )
    if pattern.search(existing):
        return pattern.sub(new_section, existing, count=1)
    # Prepend after the file's `# Changelog` H1 + any intro paragraphs. The
    # negative lookahead stops the intro at the first existing `## ` heading so
    # we don't greedily swallow earlier sections.
    intro_re = re.compile(r"\A(# Changelog\n(?:(?!## )[^\n]*\n)*)", re.MULTILINE)
    match = intro_re.match(existing)
    if match:
        intro = match.group(1)
        rest = existing[match.end(1):]
        sep = "" if intro.endswith("\n\n") else "\n"
        return intro + sep + new_section + ("\n" + rest if rest else "")
    return new_section + "\n" + existing


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path.cwd(),
        help="repository root (default: cwd)",
    )
    parser.add_argument(
        "--calver",
        required=True,
        help="CalVer tag for the section header (e.g. v2026.05.1)",
    )
    parser.add_argument(
        "--date",
        required=True,
        help="ISO date for the section header (e.g. 2026-05-26)",
    )
    parser.add_argument(
        "--changelog",
        type=Path,
        default=None,
        help="path to CHANGELOG.md (default: <repo-root>/CHANGELOG.md)",
    )
    args = parser.parse_args(argv)

    changelog_path = args.changelog or (args.repo_root / "CHANGELOG.md")
    manifest = load_manifest(args.repo_root)

    sections: list[tuple[str, str, dict[str, list[Commit]]]] = []
    for package_path, version in manifest.items():
        if not package_path.startswith("skills/"):
            continue
        skill = package_path[len("skills/"):]
        prev = find_prev_tag(args.repo_root, skill, version)
        commits = commits_since(args.repo_root, skill, prev)
        sections.append((skill, version, group_commits(commits)))

    new_section = format_calver_section(args.calver, args.date, sections)
    existing = (
        changelog_path.read_text(encoding="utf-8")
        if changelog_path.exists()
        else "# Changelog\n\n"
    )
    changelog_path.write_text(
        rewrite_changelog(existing, new_section, args.calver), encoding="utf-8"
    )
    print(f"wrote {changelog_path}: section {args.calver}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
