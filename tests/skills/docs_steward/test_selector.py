"""selector.select_tool — baseline preference + fallback order semantics."""

from __future__ import annotations

import unittest

from docs_steward.selector import FALLBACK_ORDER, select_tool
from docs_steward.tools import Tool

from .fakes import FakeProcessRunner


def _runner_with(*tools: Tool) -> FakeProcessRunner:
    return FakeProcessRunner(paths={t.value: f"/usr/bin/{t.value}" for t in tools})


class SelectToolTests(unittest.TestCase):
    def test_no_tools_returns_none(self) -> None:
        self.assertIsNone(select_tool("universal-subset", FakeProcessRunner()))

    def test_markdownlint_baseline_prefers_cli2(self) -> None:
        runner = _runner_with(Tool.MARKDOWNLINT_CLI2, Tool.MARKDOWNLINT, Tool.PRETTIER)
        self.assertEqual(
            select_tool(".markdownlint.json", runner), Tool.MARKDOWNLINT_CLI2
        )

    def test_markdownlint_baseline_falls_back_to_old_cli(self) -> None:
        runner = _runner_with(Tool.MARKDOWNLINT, Tool.PRETTIER)
        self.assertEqual(
            select_tool(".markdownlint.json", runner), Tool.MARKDOWNLINT
        )

    def test_prettierrc_baseline_picks_prettier(self) -> None:
        runner = _runner_with(Tool.PRETTIER, Tool.MARKDOWNLINT_CLI2)
        self.assertEqual(select_tool(".prettierrc", runner), Tool.PRETTIER)

    def test_prettier_config_dot_prefix(self) -> None:
        runner = _runner_with(Tool.PRETTIER)
        self.assertEqual(select_tool("prettier.config.js", runner), Tool.PRETTIER)

    def test_remarkrc_baseline_picks_remark(self) -> None:
        runner = _runner_with(Tool.REMARK)
        self.assertEqual(select_tool(".remarkrc", runner), Tool.REMARK)

    def test_dprint_baseline_picks_dprint(self) -> None:
        runner = _runner_with(Tool.DPRINT)
        self.assertEqual(select_tool("dprint.json", runner), Tool.DPRINT)

    def test_universal_subset_uses_fallback_order(self) -> None:
        runner = _runner_with(Tool.PRETTIER, Tool.MARKDOWNLINT_CLI2)
        # FALLBACK_ORDER starts with MARKDOWNLINT_CLI2, so it wins when both available.
        self.assertEqual(
            select_tool("universal-subset", runner), Tool.MARKDOWNLINT_CLI2
        )

    def test_baseline_matched_but_no_preferred_tool_falls_back(self) -> None:
        # Baseline declares markdownlint but neither markdownlint binary is on PATH.
        runner = _runner_with(Tool.PRETTIER)
        self.assertEqual(select_tool(".markdownlint.json", runner), Tool.PRETTIER)

    def test_fallback_order_is_non_empty(self) -> None:
        self.assertGreater(len(FALLBACK_ORDER), 0)


if __name__ == "__main__":
    unittest.main()
