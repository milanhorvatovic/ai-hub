"""One definition of "a fenced code sample" for every lane that checks one.

Two suites read fences now — the per-skill python/bash lane and the fleet-wide
typescript lane — and a second copy of this regex is the failure mode the lanes
exist to catch, one level up: a lane keyed to a spelling the content stopped
using goes dark while still reporting green.
"""

from __future__ import annotations

import re
import textwrap
from pathlib import Path

# Captures indented fences too (a suggestion nested in a list item) and remembers
# the indent so the closing fence must match it. A ````-opened block never starts
# a match — the fourth backtick is not `\w` — so its inner fences are collected
# individually, which is what we want: they are samples in their own right.
_FENCE = re.compile(
    r"^(?P<indent>[ \t]*)```(?P<lang>\w+)[^\n]*\n(?P<body>.*?)^(?P=indent)```",
    re.M | re.S,
)

# The info string is authored for a reader, so the fleet spells one language two
# ways: `sh` beside `bash`, `ts` beside `typescript`. The lane normalizes rather
# than the content, because `sh` tells a reader "POSIX, not bash-only" and that
# distinction is worth more than a checker's convenience. Mapping `sh` onto a
# bash parser weakens the check (bash accepts what `sh` would reject) but cannot
# invent a failure, which is the direction a guard is allowed to be wrong in.
LANGUAGE_ALIASES = {"sh": "bash", "shell": "bash", "ts": "typescript", "py": "python"}


def language_of(info_string_lang: str) -> str:
    """The canonical language name for a fence's info string."""
    return LANGUAGE_ALIASES.get(info_string_lang, info_string_lang)


def fences_in(md: Path) -> list[tuple[int, str, str]]:
    """(1-based fence line, canonical language, dedented body) for one file.

    Bodies are normalized to LF. `.gitattributes` sets `* text=auto`, so markdown
    arrives CRLF on a Windows checkout, and a shell parser reads the stray `\\r`
    as part of the last token on every line.
    """
    text = md.read_text(encoding="utf-8").replace("\r\n", "\n")
    return [
        (
            text[: m.start()].count("\n") + 1,
            language_of(m.group("lang")),
            textwrap.dedent(m.group("body")),
        )
        for m in _FENCE.finditer(text)
    ]


def fences_under(root: Path, relative_to: Path | None = None) -> list[tuple[str, int, str, str]]:
    """(relative path, 1-based fence line, canonical language, body) under a tree."""
    base = relative_to or root
    return [
        # POSIX-form path so a failure reads the same on every platform.
        (md.relative_to(base).as_posix(), line, lang, body)
        for md in sorted(root.rglob("*.md"))
        for line, lang, body in fences_in(md)
    ]
