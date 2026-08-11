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
other half true. What the line scan cannot see — a flow mapping, a value on the
next line — is covered by `--verify-completeness`, which parses each file and
fails closed on any `uses:` occurrence the scan and the parse disagree about,
bound to its source line so equal values at different lines cannot cancel out.
Both passes cover workflows and composite-action manifests
(`.github/actions/**/action.y*ml`), which is what makes the local `./`
exemption sound: a local reference points at content that is itself scanned.
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
# completeness verification rather than silently skipped.
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
    """One `uses:` reference as written in a workflow or action manifest."""

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


def target_files(root: Path) -> list[Path]:
    """Workflow files and composite-action manifests under `root`'s `.github`.

    Both run with this repository's credentials, and manifests are where an
    exempt local `./` reference could otherwise smuggle a mutable remote pin.
    """
    github = root / ".github"
    return sorted(github.glob("workflows/*.y*ml")) + sorted(github.glob("actions/**/action.y*ml"))


def collect_uses(root: Path) -> list[Use]:
    """Every `uses:` reference in the target files, in file order."""
    uses: list[Use] = []
    for path in target_files(root):
        lines = path.read_text(encoding="utf-8").splitlines()
        for number, text in enumerate(lines, start=1):
            match = _USES_LINE.match(text)
            if match is None:
                continue
            comment = match["comment"]
            uses.append(
                Use(
                    path=path,
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
        return None  # same-repo content: no ref to pin, and the target is scanned

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


def scan(root: Path) -> list[Finding]:
    return [
        Finding(use.path, use.line, problem)
        for use in collect_uses(root)
        if (problem := check(use)) is not None
    ]


def yaml_uses_entries(text: str) -> list[tuple[int, str]]:
    """(line, value) for every scalar under a `uses` key, from a composed parse.

    Composed rather than loaded so each value keeps its source position — the
    completeness comparison binds occurrences to lines, so a missed reference
    cannot be cancelled by an equal-valued false positive elsewhere in the file.
    """
    import yaml

    entries: list[tuple[int, str]] = []

    def walk(node: object) -> None:
        if isinstance(node, yaml.MappingNode):
            for key, value in node.value:
                if (
                    isinstance(key, yaml.ScalarNode)
                    and key.value == "uses"
                    and isinstance(value, yaml.ScalarNode)
                ):
                    entries.append((value.start_mark.line + 1, value.value))
                walk(value)
        elif isinstance(node, yaml.SequenceNode):
            for item in node.value:
                walk(item)

    document = yaml.compose(text, Loader=yaml.SafeLoader)
    if document is not None:
        walk(document)
    return entries


def _describe(entries: list[tuple[int, str]]) -> str:
    return ", ".join(f"line {line}: {value}" for line, value in entries) or "none"


def verify_completeness(root: Path) -> list[Finding]:
    """Findings for every file where the line scan and a YAML parse disagree.

    PyYAML is imported on demand (in `yaml_uses_entries`) rather than at module
    level so the default scan stays dependency-free; the caller opting into
    verification is the one that must provide the parser, and fails loudly when
    it cannot.
    """
    scanned_by_file: dict[Path, list[tuple[int, str]]] = {}
    for use in collect_uses(root):
        scanned_by_file.setdefault(use.path, []).append((use.line, use.value))

    findings: list[Finding] = []
    for path in target_files(root):
        expected = sorted(yaml_uses_entries(path.read_text(encoding="utf-8")))
        scanned = sorted(scanned_by_file.get(path, []))
        if scanned != expected:
            findings.append(
                Finding(
                    path,
                    1,
                    "the line scan and the YAML parse disagree on this file's `uses:` references "
                    f"(scan: {_describe(scanned)}; parse: {_describe(expected)}) — write every reference "
                    "as a plain inline `uses: value` scalar so the pin and its trailing comment stay checkable",
                )
            )
    return findings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "root",
        nargs="?",
        type=Path,
        default=Path(__file__).resolve().parents[2],
        help="repository root whose .github workflows and composite actions to scan (default: this repository)",
    )
    parser.add_argument(
        "--annotate",
        action="store_true",
        help="emit GitHub error annotations alongside the plain report",
    )
    parser.add_argument(
        "--verify-completeness",
        action="store_true",
        help="also parse each file with PyYAML and fail on any `uses:` the line scan disagrees about",
    )
    args = parser.parse_args(argv)

    if not args.root.is_dir():
        print(f"not a directory: {args.root}", file=sys.stderr)
        return 2

    findings = scan(args.root)
    if args.verify_completeness:
        findings += verify_completeness(args.root)
    for finding in findings:
        print(f"{finding.path}:{finding.line}: {finding.problem}", file=sys.stderr)
        if args.annotate:
            print(f"::error file={finding.path},line={finding.line}::{finding.problem}")

    if findings:
        return 1
    print(f"All action references under {args.root} are SHA-pinned with maintainable version comments.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
