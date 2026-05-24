#!/usr/bin/env python3
"""Entry shim — runs docs_steward.cli as `recommend-tools`."""

import sys
from pathlib import Path


def main() -> int:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from docs_steward.cli import main as cli_main  # deferred: needs sys.path first
    return cli_main(["recommend-tools", *sys.argv[1:]])


if __name__ == "__main__":
    raise SystemExit(main())
