"""What a skill costs to discover and to load, in bytes that do not move.

Three numbers, because the two the foundry's `stats.py` puts in its headline
answer different questions from the one this repo keeps growing. `discovery`
sums every frontmatter block, so it prices being findable across the fleet;
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

Every count normalizes CRLF to LF first. `.gitattributes` checks markdown out
native, so the Windows legs of the test matrix read the same content a byte per
line heavier — around 1.5% on a skill tree, which is more than twice the largest
real growth step this program has produced. Raw counts would put a platform
default where the signal belongs and fail those legs on the first run.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path

from tests.support.reachability import reachable_files

_DELIMITER = b"---\n"

# Reached but not loaded. A skill points at these so a tool or a human can open
# one; they are never pulled into context the way a reference is, so billing
# them would price the wrong thing.
_NOT_LOADED = frozenset({"assets", "scripts"})


def lf_bytes(path: Path) -> int:
    """Byte length of `path` with CRLF normalized to LF."""
    return len(path.read_bytes().replace(b"\r\n", b"\n"))


def frontmatter_bytes(path: Path) -> int:
    """Bytes of the file's opening YAML frontmatter block, 0 when it has none.

    The block runs from the opening delimiter through the newline that ends the
    closing one, which is the span the foundry's `discovery_bytes` counts.
    """
    data = path.read_bytes().replace(b"\r\n", b"\n")
    if not data.startswith(_DELIMITER):
        return 0
    closing = data.find(b"\n---", len(_DELIMITER) - 1)
    if closing == -1:
        return 0
    end_of_line = data.find(b"\n", closing + 1)
    return len(data) if end_of_line == -1 else end_of_line + 1


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

    def is_skill_content(path: Path) -> bool:
        return _NOT_LOADED.isdisjoint(path.relative_to(inside).parts)

    loaded = {path for path in reachable_files(skill) if is_skill_content(path)}
    return ContextCost(
        discovery_bytes=sum(
            frontmatter_bytes(md)
            for md in skill.rglob("*.md")
            if is_skill_content(md.resolve())
        ),
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
