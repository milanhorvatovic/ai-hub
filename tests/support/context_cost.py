"""What a skill costs to discover and to load, in bytes that do not move.

Three numbers, because the two the foundry's `stats.py` puts in its headline
answer different questions from the one this repo keeps growing. `discovery`
sums the frontmatter a harness reads before routing, so it prices being
findable across the fleet;
`load` is the whole reachable tree, so it prices a triggered skill in full; and
`skill_md` is the router alone — read on every task the skill takes, whatever
the language — which is where the growth worth reviewing on a PR shows up and
where a threshold would eventually attach. Against a 350 KB tree a kilobyte of
new router is a rounding error; against the router it is four percent.

These are not the foundry's numbers on every skill, and the difference is the
foundry's. Its `stats.py` reads one router table, so on a multi-table router it
never descends into the capabilities the other tables list — eleven of
git-toolkit's, twelve of oss-repository-conventions' — and reports a load up to
40% under the truth. That is the multi-table limitation this repo already tracks
upstream; where its parser sees the whole router the two agree exactly.

`skill_md` overlaps `discovery` by one block and that is deliberate: the always-
loaded cost is what the file weighs, and netting the frontmatter out to keep the
three disjoint would report a quantity nothing actually loads.

Text counts normalize CRLF to LF first. `.gitattributes` checks markdown out
native, so the Windows legs of the test matrix read the same content a byte per
line heavier — around 1.5% on a skill tree, which is larger than any single
growth step this repo has recorded. Raw counts would put a platform default
where the signal belongs and fail those legs on the first run. Files whose bytes
are not text are counted raw, because there a `\r\n` pair is payload.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path

from tests.support.reachability import reachable_files

_DELIMITER = b"---\n"

# Git's own text/binary heuristic, which is what decides the checkout this has
# to stay stable across: `.gitattributes` sets `* text=auto`, and `text=auto`
# means "normalize unless the blob looks binary", where looking binary is a NUL
# byte near the start. Matching the rule beats listing suffixes, because the
# markdown-link collector accepts any relative target — a `.csv` or an
# extensionless file is text to git, would arrive CRLF on Windows, and an
# allowlist would count it raw and fail the baseline there.
_BINARY_SNIFF_BYTES = 8000

# `.gitattributes` marks these `binary`, which is `-text` — git never normalizes
# them whatever they contain, so the content heuristic must not get a vote. A
# NUL-free JPEG holding a `\r\n` pair is the case: sniffing alone rewrites
# payload and undercounts the file. A test holds this set against the attributes
# file so the two cannot drift.
#
# Matched with case, because the attribute patterns are. `git check-attr` on a
# case-sensitive checkout reports `IMAGE.PNG` as `text: auto` — `*.png` does not
# cover it — so lowercasing here would count a file raw that git may hand over
# as CRLF, and the baseline would stop being platform-independent. Whether the
# attributes file should carry uppercase patterns is a question for that file.
_DECLARED_BINARY_SUFFIXES = frozenset({".png", ".jpg", ".pdf"})

# Payload directories: a skill ships these so a tool can be handed a file or a
# script can be run, and that is not context anyone loads. The exclusion is of
# the payload rather than the directory, because documentation lands in them
# too — docs-steward's router names `assets/configs/README.md` in the same
# breath as its references, and that file is prose about the bundled configs
# sitting beside the configs themselves. Markdown reached under a payload
# directory is read like any other markdown and is billed like any other.
_PAYLOAD_DIRECTORIES = frozenset({"assets", "scripts"})


def lf_bytes(path: Path) -> int:
    """Byte length of `path`, with CRLF normalized to LF in text files only.

    A `\r\n` pair is a line ending in markdown and a value in a PNG, so payload
    is counted raw: rewriting pairs inside it would report the file smaller than
    it loads, silently. The split follows git's rules, since git is what decides
    how the file arrives — an explicit `binary` attribute first, because that
    setting means never normalize whatever the content looks like, and then
    `text=auto`'s own heuristic, where a blob is binary when a NUL byte appears
    near its start.
    """
    data = path.read_bytes()
    if path.suffix in _DECLARED_BINARY_SUFFIXES:
        return len(data)
    if b"\x00" in data[:_BINARY_SNIFF_BYTES]:
        return len(data)
    return len(data.replace(b"\r\n", b"\n"))


def discovery_contributors(skill: Path):
    """The files read before routing: the router, and every capability entry on
    disk whether the router reaches it or not.

    Not every markdown file with frontmatter. A reference is opened after
    routing has already happened, so its frontmatter — if one ever carries any —
    is a load cost and not a discovery cost. Verified against the pinned
    foundry, which bills exactly these two positions.
    """
    yield skill / "SKILL.md"
    yield from sorted(skill.glob("capabilities/*/capability.md"))


def frontmatter_bytes(path: Path) -> int:
    """Bytes of the file's opening YAML frontmatter block, 0 when it has none.

    The block runs from the opening delimiter through the newline that ends the
    closing one, which is the span the foundry's `discovery_bytes` counts.

    The closing delimiter is a line that *is* `---`, not one that starts with
    it. Scanning for the prefix ends the block early on a value like
    `---note: y`, and invents a block entirely in a file that merely opens with
    a thematic break and closes with `----` further down.
    """
    data = path.read_bytes().replace(b"\r\n", b"\n")
    if not data.startswith(_DELIMITER):
        return 0

    offset = len(_DELIMITER)
    while offset <= len(data):
        break_at = data.find(b"\n", offset)
        line = data[offset:] if break_at == -1 else data[offset:break_at]
        if line == b"---":
            return len(data) if break_at == -1 else break_at + 1
        if break_at == -1:
            return 0
        offset = break_at + 1
    return 0


@dataclass(frozen=True)
class ContextCost:
    discovery_bytes: int
    skill_md_bytes: int
    load_bytes: int
    files: int

    def as_baseline(self) -> dict[str, int]:
        return asdict(self)


def measure(skill: Path) -> ContextCost:
    """Measure one skill directory.

    `load` and `files` cover the tree `reachable_files` walks, so the cost
    reported and the reachability the structural suite asserts come from one
    walk — a file nothing routes to is not billed, and cannot be, without the
    two disagreeing.

    Discovery is the exception, and reads the directory instead. What a harness
    pays to know a skill exists is a property of the files on disk: an unrouted
    capability still ships a frontmatter block and still costs whoever scans it.
    Walking for that number would make it right only for as long as the orphan
    checks hold, and a measurement should not rest on another guard's invariant.
    """
    inside = skill.resolve()

    def is_loaded(path: Path) -> bool:
        # First component only: the payload directories are top-level in a
        # skill, so `references/scripts/guide.md` is a reference that happens to
        # sit in a directory sharing the name, not a script.
        if path.relative_to(inside).parts[0] not in _PAYLOAD_DIRECTORIES:
            return True
        return path.suffix == ".md"

    loaded = {path for path in reachable_files(skill) if is_loaded(path)}
    return ContextCost(
        discovery_bytes=sum(frontmatter_bytes(md) for md in discovery_contributors(skill)),
        skill_md_bytes=lf_bytes(skill / "SKILL.md"),
        load_bytes=sum(lf_bytes(path) for path in loaded),
        files=len(loaded),
    )


def baseline_for(skills_root: Path) -> dict[str, dict[str, int]]:
    """The whole fleet's costs, in the shape the committed baseline stores."""
    return {
        skill_md.parent.name: measure(skill_md.parent).as_baseline()
        for skill_md in sorted(skills_root.glob("*/SKILL.md"))
    }


if __name__ == "__main__":  # refresh path named by the guard's failure message
    import json
    import sys

    root = Path(__file__).resolve().parents[2]
    target = root / "tests" / "skills" / "context-cost-baseline.json"
    target.write_text(json.dumps(baseline_for(root / "skills"), indent=2) + "\n")
    print(f"wrote {target.relative_to(root)}", file=sys.stderr)
