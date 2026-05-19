"""priority.INSTALL_PRIORITY + hints.install_hints — invariants on the data."""

from __future__ import annotations

import unittest

from docs_steward.hints import install_hints
from docs_steward.priority import INSTALL_PRIORITY
from docs_steward.tools import SUPPORTED_TOOLS, Tool


class PriorityTests(unittest.TestCase):
    def test_priority_is_non_empty(self) -> None:
        self.assertGreater(len(INSTALL_PRIORITY), 0)

    def test_priority_entries_are_unique(self) -> None:
        self.assertEqual(len(INSTALL_PRIORITY), len(set(INSTALL_PRIORITY)))

    def test_priority_only_references_known_tools(self) -> None:
        for tool in INSTALL_PRIORITY:
            self.assertIn(tool, SUPPORTED_TOOLS)

    def test_prettier_is_top_priority(self) -> None:
        # Documented preference: prettier for the widest ecosystem fit.
        self.assertEqual(INSTALL_PRIORITY[0], Tool.PRETTIER)


class InstallHintsTests(unittest.TestCase):
    def test_every_priority_tool_has_hints(self) -> None:
        for tool in INSTALL_PRIORITY:
            with self.subTest(tool=tool):
                hints = install_hints(tool)
                self.assertGreater(
                    len(hints), 0, f"{tool.value} has no install hints"
                )

    def test_every_supported_tool_has_hints(self) -> None:
        for tool in SUPPORTED_TOOLS:
            with self.subTest(tool=tool):
                self.assertGreater(len(install_hints(tool)), 0)

    def test_unknown_tool_returns_empty_tuple(self) -> None:
        self.assertEqual(install_hints("not-a-tool"), ())  # type: ignore[arg-type]


if __name__ == "__main__":
    unittest.main()
