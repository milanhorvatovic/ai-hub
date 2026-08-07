"""Helpers shared by more than one suite under `tests/`.

Anything here is imported by at least two test modules. A helper used by one
suite stays in that suite — this package exists to stop a second copy of a
definition, not to collect utilities.
"""
