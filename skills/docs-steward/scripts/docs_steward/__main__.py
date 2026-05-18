"""Enables `python -m docs_steward <subcommand>`."""

import sys

from .cli import main

if __name__ == "__main__":
    sys.exit(main())
