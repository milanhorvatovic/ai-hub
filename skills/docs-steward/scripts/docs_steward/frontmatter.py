"""Extract YAML-shaped blocks from markdown source text.

Two block kinds are recognized:

- **Frontmatter** — file opens with a `---` line, content runs until the next
  `---` (or `...`) line. At most one per file. Source kind = `frontmatter`.
- **Fenced YAML** — fenced code block with `yaml` or `yml` language tag.
  Source kind = `fenced`. Any number per file.

All parsing is pure and stdlib-only — no markdown AST library. The grammar
handled here is the strict-enough subset CommonMark + GitHub Flavored
Markdown agree on for code-fence + frontmatter detection.

Anchors follow the no-line-numbers convention (per SKILL.md): the locator
is human-readable text (block kind for frontmatter; first non-empty content
line truncated for fenced blocks), not file:line.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal


BlockKind = Literal["frontmatter", "fenced"]

_FRONTMATTER_BOUNDARY = re.compile(r"^(?:---|\.\.\.)\s*$")
# Opening fence: 0-3 leading spaces (CommonMark permits indented fences),
# 3+ backticks or tildes, optional whitespace, ya?ml language tag, then
# either EOL or whitespace followed by an info-string (e.g.
# ``` ```yaml linenums="1" ``` or ``` ```yaml title="example" ```). CommonMark
# allows arbitrary info-string content after the language tag; the previous
# `\s*$` anchor rejected any non-whitespace and silently skipped those blocks.
_FENCE_OPEN = re.compile(
    r"^ {0,3}(`{3,}|~{3,})\s*(ya?ml)(?:\s+.*)?\s*$", re.IGNORECASE,
)
# Closing fence: 0-3 leading spaces (independent of the opener's indent
# per CommonMark), same character as opener, length >= opener's length,
# then only whitespace until EOL. CommonMark explicitly permits the closer
# to be longer than the opener; the previous `re.escape(open_match.group(1))`
# anchor required exact length and silently skipped any block where the
# closer was longer (treating it as unterminated).
_FENCE_CLOSE_TPL = "^ {{0,3}}{fence_char}{{{fence_len},}}\\s*$"


@dataclass(frozen=True)
class FrontmatterBlock:
    """A YAML-shaped block extracted from markdown source.

    `kind` distinguishes top-of-file frontmatter from fenced YAML blocks.
    `yaml_text` is the YAML content with surrounding `---` / fence lines
    stripped. `anchor` is a short locator suitable for `<RULE>` citation —
    e.g. `"frontmatter"` or `"yaml fence: <first-line excerpt>"` — chosen
    to be stable across edits (no line numbers per SKILL.md convention).
    """

    kind: BlockKind
    yaml_text: str
    anchor: str


def _extract_frontmatter(lines: list[str]) -> tuple[FrontmatterBlock | None, int]:
    """Return (block, lines_consumed). Lines consumed includes both delimiters.
    Block is None when the file does not open with frontmatter."""
    if not lines or not _FRONTMATTER_BOUNDARY.match(lines[0]):
        return None, 0
    for end_idx in range(1, len(lines)):
        if _FRONTMATTER_BOUNDARY.match(lines[end_idx]):
            yaml_text = "\n".join(lines[1:end_idx])
            return FrontmatterBlock("frontmatter", yaml_text, "frontmatter"), end_idx + 1
    # Unterminated frontmatter — not a frontmatter block; do not consume.
    return None, 0


def _extract_fenced(lines: list[str], offset: int) -> list[FrontmatterBlock]:
    """Find every yaml/yml-tagged fenced code block from `offset` onward.
    A fenced block opens with ``` ```yaml ``` or ``` ~~~yaml ``` and closes
    with a matching fence of equal-or-greater length on its own line."""
    blocks: list[FrontmatterBlock] = []
    i = offset
    while i < len(lines):
        open_match = _FENCE_OPEN.match(lines[i])
        if not open_match:
            i += 1
            continue
        fence = open_match.group(1)
        close_re = re.compile(
            _FENCE_CLOSE_TPL.format(
                fence_char=re.escape(fence[0]),
                fence_len=len(fence),
            )
        )
        # Scan forward for closing fence; bail if EOF reached (malformed block).
        end_idx = i + 1
        while end_idx < len(lines) and not close_re.match(lines[end_idx]):
            end_idx += 1
        if end_idx >= len(lines):
            # Unterminated yaml opener — advance past it and keep scanning.
            # Earlier the loop `break`-ed out here, silently dropping every
            # well-formed yaml fence later in the file. The skill prefers
            # auditing as many parseable blocks as possible even when the
            # surrounding markdown has an authoring mistake; the strict
            # CommonMark "unclosed fence consumes rest of document"
            # behaviour would mask later legitimate yaml blocks from
            # md-audit-frontmatter without recourse.
            i += 1
            continue
        yaml_text = "\n".join(lines[i + 1 : end_idx])
        anchor = _first_nonempty(yaml_text, fallback=f"yaml fence #{len(blocks) + 1}")
        blocks.append(FrontmatterBlock("fenced", yaml_text, f"yaml fence: {anchor}"))
        i = end_idx + 1
    return blocks


def _first_nonempty(text: str, fallback: str, max_chars: int = 40) -> str:
    for line in text.splitlines():
        stripped = line.strip()
        if stripped:
            return stripped[:max_chars] + ("…" if len(stripped) > max_chars else "")
    return fallback


def extract_blocks(text: str) -> list[FrontmatterBlock]:
    """Return every YAML-shaped block in `text`, frontmatter first (when
    present) then fenced YAML blocks in source order. Empty list when no
    blocks are present."""
    lines = text.splitlines()
    blocks: list[FrontmatterBlock] = []
    front, consumed = _extract_frontmatter(lines)
    if front is not None:
        blocks.append(front)
    blocks.extend(_extract_fenced(lines, consumed))
    return blocks
