#!/usr/bin/env python3
"""Entry shim — runs docs_steward.cli as `md-audit-frontmatter`."""

import sys
from pathlib import Path


def main() -> int:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from docs_steward.cli import main as cli_main  # deferred: needs sys.path first
    return cli_main(["md-audit-frontmatter", *sys.argv[1:]])


if __name__ == "__main__":
    raise SystemExit(main())
