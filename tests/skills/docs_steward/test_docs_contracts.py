"""Doc-vs-code contracts for docs-steward.

The skill's markdown states two facts the code owns: the formatter fallback
order (`selector.FALLBACK_ORDER`) and the CLI flag surface
(`cli._build_parser`). Nothing kept them in sync — the 2026-07-10 audit found
`references/formatter-tools.md` documenting a stale markdownlint-first
fallback order (finding 1) while the code and SKILL.md say prettier-first.
These tests pin doc to code so the next reorder or flag rename cannot drift
silently.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

import pytest
from docs_steward import selector
from docs_steward.cli import _build_parser

_SKILL_ROOT = Path(__file__).resolve().parents[3] / "skills" / "docs-steward"

_CODE_ORDER = tuple(tool.value for tool in selector.FALLBACK_ORDER)

# An order statement is a backtick arrow chain naming exactly the fallback
# tool set: `prettier` → `markdownlint-cli2` → … Shorter tool chains in prose
# (e.g. a two-tool family preference) are not fallback-order statements.
_ARROW_CHAIN = re.compile(r"`[a-z0-9-]+`(?:\s*→\s*`[a-z0-9-]+`)+")
_BACKTICK_TOKEN = re.compile(r"`([a-z0-9-]+)`")

_FLAG = re.compile(r"--[a-z][a-z0-9-]*")

# The skill's own executables; a cheatsheet line mentioning none of these is
# an external-tool invocation (pytest, coverage, git) whose flags are not ours.
_ENTRY_POINTS = (
    "md-audit.py",
    "md-format.py",
    "md-fix.py",
    "md-audit-frontmatter.py",
    "probe.py",
    "recommend-tools.py",
    "-m docs_steward",
)


def _documented_order_statements() -> list[tuple[str, int, tuple[str, ...]]]:
    """(file, line, chain) for every full-tool-set arrow chain in the docs."""
    statements = []
    for doc in (_SKILL_ROOT / "SKILL.md", _SKILL_ROOT / "references" / "formatter-tools.md"):
        for lineno, line in enumerate(doc.read_text(encoding="utf-8").splitlines(), start=1):
            for chain_match in _ARROW_CHAIN.finditer(line):
                chain = tuple(_BACKTICK_TOKEN.findall(chain_match.group(0)))
                if set(chain) == set(_CODE_ORDER):
                    statements.append((doc.name, lineno, chain))
    return statements


@pytest.mark.xfail(
    reason=(
        "S1 skills-spec-compliance-sweep: references/formatter-tools.md:18 "
        "documents markdownlint-first; selector.FALLBACK_ORDER is "
        "prettier-first (audit docs-steward finding 1)"
    ),
    strict=True,
)
def test_documented_fallback_order_matches_selector() -> None:
    statements = _documented_order_statements()
    assert len(statements) >= 2, (
        "expected fallback-order statements in both SKILL.md and "
        f"formatter-tools.md, found {len(statements)}"
    )
    stale = [
        f"{name}:{lineno} documents {' -> '.join(chain)}"
        for name, lineno, chain in statements
        if chain != _CODE_ORDER
    ]
    assert not stale, (
        f"docs disagree with selector.FALLBACK_ORDER {' -> '.join(_CODE_ORDER)}:\n"
        + "\n".join(stale)
    )


def _parser_flags(parser: argparse.ArgumentParser) -> set[str]:
    # argparse offers no public introspection; _actions/_SubParsersAction is
    # the standard idiom and stable across supported Python versions.
    flags: set[str] = set()
    for action in parser._actions:
        flags.update(opt for opt in action.option_strings if opt.startswith("--"))
        if isinstance(action, argparse._SubParsersAction):
            for sub_parser in action.choices.values():
                flags.update(_parser_flags(sub_parser))
    return flags


def _documented_flags() -> dict[str, str]:
    """flag -> first documenting line, from usage.md's fenced invocation lines
    that call one of the skill's own entry points (comments stripped, so a
    trailing remark about an external formatter's flag is not harvested)."""
    documented: dict[str, str] = {}
    in_fence = False
    for line in (_SKILL_ROOT / "references" / "usage.md").read_text(encoding="utf-8").splitlines():
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
            continue
        command = line.split("#", 1)[0]
        if not in_fence or not any(entry in command for entry in _ENTRY_POINTS):
            continue
        for flag_match in _FLAG.finditer(command):
            documented.setdefault(flag_match.group(0), line.strip())
    return documented


def test_documented_cli_flags_exist_in_parser() -> None:
    known = _parser_flags(_build_parser())
    documented = _documented_flags()
    assert documented, "usage.md documents no flags for the skill's entry points"
    unknown = {flag: line for flag, line in documented.items() if flag not in known}
    assert not unknown, "usage.md documents flags the CLI does not define:\n" + "\n".join(
        f"{flag}: {line}" for flag, line in sorted(unknown.items())
    )
