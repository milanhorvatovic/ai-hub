#!/usr/bin/env python3
"""Entry shim — delegates to docs_steward.cli with 'recommend-tools' prepended."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import after the sys.path insert so the bundled docs_steward package resolves.
from docs_steward.cli import main

sys.exit(main(["recommend-tools", *sys.argv[1:]]))
