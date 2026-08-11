#!/usr/bin/env python3
"""Enforce full-commit-SHA action pins with a same-line version comment.

A `uses:` reference pinned to a tag or branch (`@v4`, `@main`) resolves at run
time to whatever that ref then points at, so it executes third-party code chosen
after review; a 40-hex commit SHA freezes what was reviewed. The readable half
of the convention is a trailing `# vX.Y.Z` comment on the `uses:` line itself —
the one position Dependabot rewrites when it bumps the pin. Version comments on
the line above are where this repo's rotted: Dependabot cannot see them, so five
of seven drifted from their pins, four by at least a major version.

The scan is text-level on purpose: comment placement does not survive YAML
parsing, so a parser cannot check the half of the convention that keeps the
other half true. Completeness is cross-checked in `tests/repo/test_action_pins.py`
against a real YAML parse, so a `uses:` value this scan misses fails the suite
instead of going quietly unchecked.
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path

# `uses:` or `- uses:` with an optionally quoted value and an optional trailing
# comment. `uses:` values are plain one-line scalars in practice; anything
# fancier (aliases, block scalars) escapes this shape and is caught by the
# suite's YAML cross-check rather than silently skipped.
_USES_LINE = re.compile(
    r"""^\s*(?:-\s+)?uses:\s*(?P<quote>["']?)(?P<value>[^\s"'#]+)(?P=quote)\s*(?:\#(?P<comment>.*))?$"""
)

_FULL_SHA = re.compile(r"^[0-9a-f]{40}$")

# A bare version or tag token (`v6.0.2`, `3.1.0`, `v5.0.0-rc1`) — the shape
# Dependabot recognizes and rewrites on bump. Prose would freeze while the pin
# moves, which is the rot this whole check exists to prevent.
_VERSION_TOKEN = re.compile(r"^v?\d[\w.+-]*$")

# A dotted version literal in the comment line directly above a pin — the
# rotting form this repo is migrating away from; only the trailing position
# stays maintained.
_VERSION_ABOVE = re.compile(r"\bv?\d+\.\d+")


@dataclass(frozen=True)
class Use:
    """One `uses:` reference as written in a workflow file."""

    path: Path
    line: int
    value: str
    comment: str | None
    preceding: str


@dataclass(frozen=True)
class Finding:
    path: Path
    line: int
    problem: str


def collect_uses(workflow_dir: Path) -> list[Use]:
    """Every `uses:` reference in the directory's workflows, in file order."""
    uses: list[Use] = []
    for workflow in sorted(workflow_dir.glob("*.y*ml")):
        lines = workflow.read_text(encoding="utf-8").splitlines()
        for number, text in enumerate(lines, start=1):
            match = _USES_LINE.match(text)
            if match is None:
                continue
            comment = match["comment"]
            uses.append(
                Use(
                    path=workflow,
                    line=number,
                    value=match["value"],
                    comment=comment.strip() if comment is not None else None,
                    preceding=lines[number - 2] if number > 1 else "",
                )
            )
    return uses


def check(use: Use) -> str | None:
    """The problem with this reference, or None when it meets the convention."""
    if use.value.startswith("./"):
        return None  # same-repo content: there is no ref to pin

    if use.value.startswith("docker://"):
        if "@sha256:" in use.value:
            return None
        return f"docker reference {use.value!r} must be pinned by digest (docker://image@sha256:…)"

    _, at, ref = use.value.rpartition("@")
    if not at:
        return f"{use.value!r} has no ref at all — pin it to a full commit SHA"
    if not _FULL_SHA.fullmatch(ref):
        return f"ref {ref!r} is not a full 40-hex commit SHA"

    if use.comment is None:
        return "SHA pin carries no trailing version comment (`# vX.Y.Z` on the same line)"
    if not _VERSION_TOKEN.fullmatch(use.comment):
        return f"trailing comment {use.comment!r} is not a bare version token Dependabot can maintain"

    stripped_above = use.preceding.strip()
    if stripped_above.startswith("#") and _VERSION_ABOVE.search(stripped_above):
        return "version-shaped comment on the line above the pin — Dependabot cannot maintain it there, so it rots; keep only the trailing comment"

    return None


def scan(workflow_dir: Path) -> list[Finding]:
    return [
        Finding(use.path, use.line, problem)
        for use in collect_uses(workflow_dir)
        if (problem := check(use)) is not None
    ]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "workflow_dir",
        nargs="?",
        type=Path,
        default=Path(__file__).resolve().parents[2] / ".github" / "workflows",
        help="directory of workflow files to scan (default: this repository's)",
    )
    parser.add_argument(
        "--annotate",
        action="store_true",
        help="emit GitHub error annotations alongside the plain report",
    )
    args = parser.parse_args(argv)

    if not args.workflow_dir.is_dir():
        print(f"not a directory: {args.workflow_dir}", file=sys.stderr)
        return 2

    findings = scan(args.workflow_dir)
    for finding in findings:
        print(f"{finding.path}:{finding.line}: {finding.problem}", file=sys.stderr)
        if args.annotate:
            print(f"::error file={finding.path},line={finding.line}::{finding.problem}")

    if findings:
        return 1
    print(f"All action references in {args.workflow_dir} are SHA-pinned with maintainable version comments.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
