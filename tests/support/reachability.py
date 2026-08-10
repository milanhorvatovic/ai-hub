"""One definition of "reachable from the router" for every check that needs one.

Two things depend on this walk now — the guard that every shared reference is
reachable, and the load-cost measurement whose whole subject is the set of files
a triggered skill pulls in. A second copy would let the two disagree about what
"reachable" means, and the one that drifted would keep reporting a number while
measuring a different tree. That is the same failure the sample lanes keep
`tests/support/fences.py` around to prevent, one level up.

The collectors read prose lines only, so a pointer-shaped string inside a fenced
example is prose to every caller at once.
"""

from __future__ import annotations

import re
from pathlib import Path

CAPABILITY_PATH = re.compile(r"capabilities/([a-z0-9-]+)/capability\.md")

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

def prose_lines(md_file: Path):
    """Yield (lineno, line) for lines outside fenced code blocks — fenced
    content is data (worked examples, scaffold templates), not skill
    navigation, so its link-shaped text is never a pointer.

    Per CommonMark, a fence closes only on a same-character run at least as
    long as the opener with nothing after it — so a ````-fenced block can
    embed ``` lines as content without ending the fence early. Fence-like
    lines that don't close (shorter run, other char, trailing info string)
    are fenced content and are skipped, not yielded.
    """
    open_fence: tuple[str, int] | None = None  # (fence char, opener length)
    for lineno, line in enumerate(md_file.read_text(encoding="utf-8").splitlines(), start=1):
        if m := _FENCE.match(line):
            marker = m.group(1)
            if open_fence is None:
                open_fence = (marker[0], len(marker))
            elif (
                marker[0] == open_fence[0]
                and len(marker) >= open_fence[1]
                and not line[m.end() :].strip()
            ):
                open_fence = None
            continue
        if open_fence is None:
            yield lineno, line


def backtick_paths(md_file: Path) -> list[tuple[str, int]]:
    """(token, 1-based line) for every backtick-quoted skill-internal path.

    Only `/`-bearing tokens whose first segment is a `../` traversal or a
    skill-content directory are pointers; bare filenames and external repo
    paths are prose mentions. Resolution is file-relative (the foundry rule
    and the house convention from git-toolkit's reference tests).
    """
    out: list[tuple[str, int]] = []
    for lineno, line in prose_lines(md_file):
        for m in _BACKTICK_TOKEN.finditer(line):
            token = m.group(1)
            if "/" in token and token.split("/", 1)[0] in _INTERNAL_FIRST_SEGMENTS:
                out.append((token, lineno))
    return out


def markdown_links(md_file: Path) -> list[tuple[str, int]]:
    """(target, 1-based line) for every relative markdown-link target."""
    out: list[tuple[str, int]] = []
    for lineno, line in prose_lines(md_file):
        for m in _MARKDOWN_LINK.finditer(line):
            target = m.group(1)
            if "://" in target or target.startswith(("mailto:", "/")):
                continue
            out.append((target, lineno))
    return out

def reachable_files(skill: Path) -> set[Path]:
    """Every file reachable from `SKILL.md` by following pointers transitively.

    Edges are the router's capability rows plus the backtick paths and
    relative markdown links the resolution checks already collect, so a link
    that resolves and a link that carries reachability are the same link —
    and a filename inside a fenced example is prose to both, since every
    collector here reads prose lines only.

    Capability rows are read from `SKILL.md` alone, because routing is the
    only place a capability edge legitimately comes from: a capability named
    in passing by some other file is a mention, not navigation. Scanning them
    everywhere cannot mask an orphan today — the routing checks already put
    every capability in the router — but it would make this walk correct only
    for as long as that other guard holds, and a reachability check should
    not borrow its answer from one.

    The walk also never leaves the skill directory, for the same reason and a
    second one. A route that goes out to a repo-level document and back in
    would make an orphan look reachable over a path that does not exist once
    the skill is installed, since only `skills/<name>/` ships. No skill can
    point outward today — the resolution checks reject a pointer that escapes
    the tree — so this is again a borrowed invariant made local.

    Traversal follows markdown only, because a schema or a sample carries no
    pointers to follow, but the result includes every kind of file a pointer
    lands on: they are reached, and a caller measuring what a triggered skill
    costs has to count them.
    """
    inside = skill.resolve()
    root = (skill / "SKILL.md").resolve()
    seen: set[Path] = set()
    queue = [root]
    while queue:
        current = queue.pop()
        if current in seen or not current.is_file():
            continue
        seen.add(current)
        if current.suffix != ".md":
            continue
        targets = [
            current.parent / token
            for token, _ in backtick_paths(current) + markdown_links(current)
        ]
        if current == root:
            targets += [
                skill / m.group(0)
                for _, line in prose_lines(current)
                for m in CAPABILITY_PATH.finditer(line)
            ]
        queue += [
            t
            for t in (candidate.resolve() for candidate in targets)
            if t.is_relative_to(inside)
        ]
    return seen


def reachable_markdown(skill: Path) -> set[Path]:
    """The markdown subset of `reachable_files` — what the structural guards
    assert about, since only markdown carries the pointers they check."""
    return {path for path in reachable_files(skill) if path.suffix == ".md"}
