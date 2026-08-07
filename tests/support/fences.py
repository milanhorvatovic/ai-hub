"""One definition of "a fenced code sample" for every lane that checks one.

Two suites read fences now — the fleet-wide sample lanes and the worked-review
anchor check — and a second copy of this regex is the failure mode the lanes
exist to catch, one level up: a lane keyed to a spelling the content stopped
using goes dark while still reporting green.
"""

from __future__ import annotations

import re
import subprocess
import textwrap
from functools import cache
from pathlib import Path
from typing import NamedTuple

# Captures indented fences too (a suggestion nested in a list item) and remembers
# the indent so the closing fence must match it. A ````-opened block never starts
# a match — the fourth backtick is not `\w` — so its inner fences are collected
# individually, which is what we want: they are samples in their own right.
_FENCE = re.compile(
    r"^(?P<indent>[ \t]*)```(?P<lang>\w+)(?P<info>[^\n]*)\n(?P<body>.*?)^(?P=indent)```",
    re.M | re.S,
)

# The info string is authored for a reader, so the fleet spells one language two
# ways: `sh` beside `bash`, `ts` beside `typescript`. The lane normalizes rather
# than the content, because `sh` tells a reader "POSIX, not bash-only" and that
# distinction is worth more than a checker's convenience. Mapping `sh` onto a
# bash parser weakens the check (bash accepts what `sh` would reject) but cannot
# invent a failure, which is the direction a guard is allowed to be wrong in.
# Only spellings the fleet actually uses are mapped. A speculative entry for a
# spelling nobody writes cannot be tested, and the case it guards against is
# covered better from the other side: `test_every_fence_spelling_is_accounted_for`
# fails on any new spelling until someone maps it or declares it unchecked.
LANGUAGE_ALIASES = {"sh": "bash", "ts": "typescript"}

# A fence whose body is a shape to fill in rather than a command to run: it
# carries `<placeholder>` tokens a parser reads as syntax. The marker is opt-in
# and stated at the fence, so a new template fence fails the lane until someone
# marks it — the alternative, inferring template-ness from the presence of a
# `<WORD>`, silently exempts a real syntax error that happens to sit next to one.
TEMPLATE_MARKER = "template"


class Fence(NamedTuple):
    """One fenced code block, located and classified."""

    path: str
    """Path as authored for a human, POSIX-form so failures read the same everywhere."""
    line: int
    """1-based line of the opening fence."""
    language: str
    """Canonical language name, aliases already resolved."""
    body: str
    """Fence contents, dedented and LF-normalized."""
    is_template: bool
    """True when the info string marks this as a shape to fill in, not a runnable sample."""
    raw_language: str
    """The spelling as authored, kept so a lane can prove it still reaches both spellings."""


def language_of(info_string_lang: str) -> str:
    """The canonical language name for a fence's info string."""
    return LANGUAGE_ALIASES.get(info_string_lang, info_string_lang)


def fences_in(md: Path, path: str | None = None) -> list[Fence]:
    """Every fenced block in one markdown file.

    Bodies are normalized to LF. `.gitattributes` sets `* text=auto`, so markdown
    arrives CRLF on a Windows checkout, and a shell parser reads the stray `\\r`
    as part of the last token on every line.
    """
    text = md.read_text(encoding="utf-8").replace("\r\n", "\n")
    return [
        Fence(
            path=path if path is not None else md.as_posix(),
            line=text[: m.start()].count("\n") + 1,
            language=language_of(m.group("lang")),
            body=textwrap.dedent(m.group("body")),
            is_template=TEMPLATE_MARKER in m.group("info").split(),
            raw_language=m.group("lang"),
        )
        for m in _FENCE.finditer(text)
    ]


class GitUnavailable(RuntimeError):
    """Raised when the file list cannot be obtained, so a caller can skip rather
    than silently check a different set of files than it claims to."""


@cache
def tracked_markdown(root: Path) -> tuple[Path, ...]:
    """Every `.md` file in the working tree that is not ignored.

    Asking git rather than walking and filtering, because a hand-kept exclusion
    list is a second definition of "which files count" and `.gitignore` is the
    first. The first version of this did keep such a list, and it was already
    wrong: it named six directories where `.gitignore` names a dozen, so a
    `build/` or `htmlcov/` left behind by another tool would have been scanned
    as content. `--cached --others --exclude-standard` is precisely the set the
    formatter checks — tracked files plus new ones not yet staged, minus
    everything ignored — so a new document is checked before it is committed and
    an installed dependency's README never is.
    """
    try:
        done = subprocess.run(
            ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard", "--", "*.md"],
            cwd=root,
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError as exc:  # git is not installed at all
        raise GitUnavailable(f"could not run git: {exc}") from exc
    if done.returncode:
        raise GitUnavailable(f"git ls-files failed: {done.stderr.strip()}")

    # `-z` because a path may contain anything but NUL, and git would otherwise
    # quote and escape the awkward ones into something that no longer opens.
    names = sorted(name for name in done.stdout.split("\0") if name)
    # A deleted-but-still-tracked file is listed by `--cached`; skip rather than
    # fail, since the deletion is the contributor's intent and not a defect.
    return tuple(path for name in names if (path := root / name).is_file())


def fences_under(root: Path, relative_to: Path | None = None) -> list[Fence]:
    """Every fenced block in the tracked markdown under a tree."""
    base = relative_to or root
    return [
        fence
        for md in tracked_markdown(root)
        for fence in fences_in(md, path=md.relative_to(base).as_posix())
    ]
