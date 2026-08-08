"""Makes "required" mean required for the sample lanes.

The lanes skip when a parser is missing, which is right on a contributor's
machine and wrong in the CI job built to run them — there, a skip is a green
tick over an unchecked sample. Each lane routes its own "cannot run" path
through a helper that raises instead when `REQUIRE_SAMPLE_LANES` is set, but
that only holds for as long as every lane remembers to use it, and a new one
calling `pytest.skip` directly would opt itself out silently.

So the guarantee lives here instead, as a property of the run rather than of how
each lane happens to be written: with the variable set, a skip anywhere in the
sample-lane module is a failure regardless of what raised it.
"""

from __future__ import annotations

import os

import pytest

_REQUIRED = "REQUIRE_SAMPLE_LANES"
_SAMPLE_LANES = "test_code_samples.py"


@pytest.hookimpl(wrapper=True)
def pytest_runtest_makereport(item: pytest.Item, call: pytest.CallInfo[None]):
    report = yield

    if report.skipped and os.environ.get(_REQUIRED) and _SAMPLE_LANES in str(item.path):
        report.outcome = "failed"
        report.longrepr = (
            f"{item.nodeid} skipped while {_REQUIRED} is set.\n"
            "This job exists to be the place the parsers are present, so a skip"
            " here is an unchecked sample reported as success. Install the"
            " toolchain the skip reason names, or stop requiring the lanes.\n"
            f"skip reason: {report.longrepr}"
        )

    return report
