"""Renders the per-skill context-cost change of a pull request.

Reads the recorded costs from two points — the PR's base and its head — and
writes what moved to the job summary. Report-only by design: how much a skill
may grow is a judgment nobody has data for yet, and the blocking half already
happened in the suite, where a baseline that no longer describes the tree fails.

Both inputs are the committed baseline rather than a fresh measurement, so the
summary and the JSON diff a reviewer reads in the PR are the same numbers. That
holds because the staleness guard runs in the same job: if the recorded costs
had drifted from the tree, this step would not be reached.

Stdlib only, and a pure function of its two files — the git plumbing that
fetches the base copy stays in the workflow.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# (baseline key, column heading). Router first: it is the number read on every
# task the skill takes, so it is the one a reviewer should meet first.
COLUMNS = (
    ("skill_md_bytes", "Router"),
    ("load_bytes", "Load"),
    ("discovery_bytes", "Discovery"),
    ("files", "Files"),
)

HEADING = "### Context cost"
NO_CHANGE = "No context-cost change."


def _cell(before: int | None, after: int | None) -> str:
    if before is None:
        return f"— → {after:,} (new)"
    if after is None:
        return f"{before:,} → — (gone)"
    if before == after:
        return f"{after:,}"
    delta = after - before
    return f"{before:,} → {after:,} ({delta:+,})"


def _changed(before: dict[str, int], after: dict[str, int]) -> bool:
    return any(before.get(key) != after.get(key) for key, _ in COLUMNS)


def render(before: dict[str, dict[str, int]], after: dict[str, dict[str, int]]) -> str:
    """Markdown for every skill whose recorded cost moved; a note when none did."""
    rows = []
    for name in sorted(before.keys() | after.keys()):
        was, now = before.get(name, {}), after.get(name, {})
        if not _changed(was, now):
            continue
        cells = " | ".join(_cell(was.get(key), now.get(key)) for key, _ in COLUMNS)
        rows.append(f"| {name} | {cells} |")

    if not rows:
        return f"{HEADING}\n\n{NO_CHANGE}\n"

    headings = " | ".join(heading for _, heading in COLUMNS)
    rule = " | ".join("---" for _ in COLUMNS)
    return "\n".join([HEADING, "", f"| Skill | {headings} |", f"| --- | {rule} |", *rows, ""])


def _load(path: Path) -> dict[str, dict[str, int]]:
    """The baseline at `path`, or an empty fleet when it is absent or blank.

    A PR that introduces the baseline has no base copy to read, and that is a
    reportable state — every skill shows as new — rather than an error.
    """
    if not path.is_file() or not path.read_text(encoding="utf-8").strip():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: report_context_cost.py <base-baseline.json> <head-baseline.json>", file=sys.stderr)
        return 2
    print(render(_load(Path(argv[0])), _load(Path(argv[1]))), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
