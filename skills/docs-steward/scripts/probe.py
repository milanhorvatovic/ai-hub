#!/usr/bin/env python3
"""Entry shim — delegates to docs_steward.cli with 'probe' prepended."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from docs_steward.cli import (
    main,  # noqa: E402 — sys.path manipulation must precede import
)

sys.exit(main(["probe", *sys.argv[1:]]))
