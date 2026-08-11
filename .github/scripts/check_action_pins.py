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
other half true. What the line scan cannot see — a flow mapping, a value on
the next line — is covered by `--verify-completeness`, which parses each
workflow with PyYAML and fails closed on any `uses:` the scan disagrees about;
the gate runs with it, and `tests/repo/test_action_pins.py` holds the same
comparison against the tree. Only `.github/workflows/` is scanned: composite
actions under `.github/actions/` do not exist here, and their steps would need
this glob widened before they could rely on the gate.
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

_DOCKER_DIGEST = re.compile(r"^docker://[^@\s]+@sha256:[0-9a-f]{64}$")

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
        if _DOCKER_DIGEST.fullmatch(use.value):
            return None
        return f"docker reference {use.value!r} must be pinned by a full digest (docker://image@sha256:<64 hex>)"

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


def yaml_uses_values(document: object) -> list[str]:
    """Every string under a `uses` key, at any depth of a parsed workflow."""
    values: list[str] = []
    if isinstance(document, dict):
        for key, value in document.items():
            if key == "uses" and isinstance(value, str):
                values.append(value)
            values.extend(yaml_uses_values(value))
    elif isinstance(document, list):
        for item in document:
            values.extend(yaml_uses_values(item))
    return values


def verify_completeness(workflow_dir: Path) -> list[Finding]:
    """Findings for every file where the line scan and a YAML parse disagree.

    PyYAML is imported here rather than at module level so the default scan
    stays dependency-free; the caller opting into verification is the one that
    must provide the parser, and fails loudly when it cannot.
    """
    import yaml

    scanned_by_file: dict[Path, list[str]] = {}
    for use in collect_uses(workflow_dir):
        scanned_by_file.setdefault(use.path, []).append(use.value)

    findings: list[Finding] = []
    for workflow in sorted(workflow_dir.glob("*.y*ml")):
        parsed = yaml.safe_load(workflow.read_text(encoding="utf-8"))
        expected = sorted(yaml_uses_values(parsed))
        scanned = sorted(scanned_by_file.get(workflow, []))
        if scanned != expected:
            findings.append(
                Finding(
                    workflow,
                    1,
                    f"the line scan and the YAML parse disagree on this file's `uses:` references (scan: {scanned}, parse: {expected}) — write every reference as a plain inline `uses: value` scalar so the pin and its trailing comment stay checkable",
                )
            )
    return findings


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
    parser.add_argument(
        "--verify-completeness",
        action="store_true",
        help="also parse each workflow with PyYAML and fail on any `uses:` the line scan disagrees about",
    )
    args = parser.parse_args(argv)

    if not args.workflow_dir.is_dir():
        print(f"not a directory: {args.workflow_dir}", file=sys.stderr)
        return 2

    findings = scan(args.workflow_dir)
    if args.verify_completeness:
        findings += verify_completeness(args.workflow_dir)
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
