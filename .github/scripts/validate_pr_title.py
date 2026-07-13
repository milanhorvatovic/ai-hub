#!/usr/bin/env python3
"""Validate a pull-request title as a Conventional Commit — the "change-intent" gate.

PRs are squash-merged, so the PR title becomes the commit subject that release-please
reads: the type drives the version bump, while component membership is by file path.
The scope, when present, must name a skill directory (it groups the changelog by skill
and keeps the PR focused) or a known repo-wide area. The title is read from the
PR_TITLE environment variable and never interpolated into a shell command, because
PR titles are attacker-controllable on fork PRs.
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

# Conventional-Commit types accepted as a declared change intent.
TYPES = {
    "feat",
    "fix",
    "docs",
    "style",
    "refactor",
    "perf",
    "test",
    "build",
    "ci",
    "chore",
    "revert",
}

# Non-skill scopes allowed for repository-wide changes.
# Keep this in sync with the set documented in CONTRIBUTING.md and AGENTS.md.
AREA_SCOPES = {"release", "repo", "deps", "ci"}

# Cap the whole title line — the Conventional-Commit header `type(scope): subject`
# (the git-toolkit ≤72-char rule applies to the first line, not just the description).
TITLE_MAX = 72

HEADER = re.compile(
    r"^(?P<type>[a-z]+)(?:\((?P<scope>[^)]+)\))?(?P<bang>!)?: (?P<subject>.+)$"
)

# Bot login patterns (case-insensitive), the single definition the commit-style linter
# reuses by importing this module. A bot login ends in `[bot]` (`dependabot[bot]`) or
# `-bot` (`renovate-bot`); a bare "bot" substring (e.g. "botanist") is deliberately not
# a match. Keep this the only copy — a second list elsewhere would drift.
BOT_LOGIN_PATTERNS = [
    r"\[bot\]$",
    r"-bot$",
]


def is_bot_login(login: str) -> bool:
    """True when `login` looks bot-authored — the shared bot predicate for both gates."""
    return any(re.search(pattern, login, re.IGNORECASE) for pattern in BOT_LOGIN_PATTERNS)


def skill_names(repo_root: Path) -> set[str]:
    """Skill directory names — the valid Conventional-Commit scopes for skill changes."""
    skills_dir = repo_root / "skills"
    if not skills_dir.is_dir():
        return set()
    return {p.name for p in skills_dir.iterdir() if (p / "SKILL.md").is_file()}


def validate(title: str, skills: set[str], noun: str = "title") -> list[str]:
    """Return a list of human-readable problems with `title`; empty means valid.

    `noun` names the line in error messages — "title" for PR titles, "subject"
    when the commit-style linter reuses this validator for commit subjects.
    """
    match = HEADER.match(title)
    if not match:
        return [
            f"{noun} is not a Conventional Commit: {title!r}",
            "expected `type: subject` or `type(scope): subject` (scope optional), "
            "e.g. `fix(git-toolkit): handle an empty diff` or `refactor: tidy the router`",
        ]

    errors: list[str] = []
    if match["type"] not in TYPES:
        errors.append(f"type {match['type']!r} is not one of {sorted(TYPES)}")

    scope = match["scope"]
    if scope is not None:
        allowed = skills | AREA_SCOPES
        if scope not in allowed:
            errors.append(
                f"scope {scope!r} must name a skill {sorted(skills)} "
                f"or a repo area {sorted(AREA_SCOPES)}"
            )

    if not match["subject"].strip():
        errors.append("subject is empty")

    if title.rstrip().endswith("."):
        errors.append(f"{noun} ends with a period")

    if len(title) > TITLE_MAX:
        errors.append(f"{noun} is {len(title)} chars; the cap is {TITLE_MAX} for the whole {noun}")

    return errors


def main() -> int:
    title = os.environ.get("PR_TITLE", "").strip()
    if not title:
        print("PR_TITLE is empty — nothing to validate.", file=sys.stderr)
        return 1

    repo_root = Path(__file__).resolve().parents[2]
    errors = validate(title, skill_names(repo_root))
    if errors:
        print(f"Invalid PR title: {title!r}", file=sys.stderr)
        for error in errors:
            print(f"  - {error}", file=sys.stderr)
        return 1

    print(f"PR title OK: {title!r}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
