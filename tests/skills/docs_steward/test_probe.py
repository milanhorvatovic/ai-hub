"""probe.probe_tools + capture_version — inventory + version normalization."""

from __future__ import annotations

import unittest

from docs_steward.events import EventType
from docs_steward.probe import capture_version, probe_tools
from docs_steward.process import ProcessResult
from docs_steward.tools import Tool

from .fakes import FakeProcessRunner


class CaptureVersionTests(unittest.TestCase):
    def test_strips_trailing_cr(self) -> None:
        runner = FakeProcessRunner(
            paths={"prettier": "/x/prettier"},
            results={("prettier", "--version"): ProcessResult(0, "3.2.5\r\n", "")},
        )
        self.assertEqual(capture_version(runner, Tool.PRETTIER), "3.2.5")

    def test_strips_surrounding_quotes(self) -> None:
        runner = FakeProcessRunner(
            paths={"prettier": "/x/prettier"},
            results={("prettier", "--version"): ProcessResult(0, '"3.2.5"\n', "")},
        )
        self.assertEqual(capture_version(runner, Tool.PRETTIER), "3.2.5")

    def test_takes_first_nonempty_line(self) -> None:
        runner = FakeProcessRunner(
            paths={"prettier": "/x/prettier"},
            results={
                ("prettier", "--version"): ProcessResult(0, "\n  \nprettier 3.2.5\nextra", ""),
            },
        )
        self.assertEqual(capture_version(runner, Tool.PRETTIER), "prettier 3.2.5")

    def test_empty_output_returns_empty_string(self) -> None:
        runner = FakeProcessRunner(
            paths={"prettier": "/x/prettier"},
            results={("prettier", "--version"): ProcessResult(0, "", "")},
        )
        self.assertEqual(capture_version(runner, Tool.PRETTIER), "")


class ProbeToolsTests(unittest.TestCase):
    def test_no_tools_emits_missing_and_exit_3(self) -> None:
        events, code = probe_tools(FakeProcessRunner())
        self.assertEqual(code, 3)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].event, EventType.MISSING)
        self.assertEqual(events[0].tool, "all")

    def test_one_tool_available_emits_one_event_exit_0(self) -> None:
        runner = FakeProcessRunner(
            paths={"prettier": "/x/prettier"},
            results={("prettier", "--version"): ProcessResult(0, "3.2.5\n", "")},
        )
        events, code = probe_tools(runner)
        self.assertEqual(code, 0)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].event, EventType.AVAILABLE)
        self.assertEqual(events[0].tool, "prettier")
        self.assertEqual(events[0].detail, "3.2.5")

    def test_multiple_tools_emit_in_catalog_order(self) -> None:
        runner = FakeProcessRunner(
            paths={
                "prettier": "/x/prettier",
                "markdownlint-cli2": "/x/markdownlint-cli2",
            },
            results={
                ("prettier", "--version"): ProcessResult(0, "3.2.5\n", ""),
                ("markdownlint-cli2", "--version"): ProcessResult(0, "0.13.0\n", ""),
            },
        )
        events, code = probe_tools(runner)
        self.assertEqual(code, 0)
        self.assertEqual([e.tool for e in events], ["markdownlint-cli2", "prettier"])


if __name__ == "__main__":
    unittest.main()
