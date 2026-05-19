"""selector.select_tool — baseline preference + fallback order semantics."""

from __future__ import annotations

import unittest

from docs_steward.selector import (
    FALLBACK_ORDER,
    baseline_belongs_to_tool,
    select_tool,
)
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

    def test_mdformat_baseline_picks_mdformat(self) -> None:
        # `.mdformat.toml` baseline must route to mdformat; otherwise
        # selection falls through to FALLBACK_ORDER and a different
        # formatter on PATH (e.g. prettier) would silently take over.
        runner = _runner_with(Tool.MDFORMAT, Tool.PRETTIER)
        self.assertEqual(select_tool(".mdformat.toml", runner), Tool.MDFORMAT)

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

    def test_absolute_baseline_path_matches_family_preference(self) -> None:
        # Regression: --baseline /repo/.prettierrc should select Prettier
        # via the prefix table, not silently fall through to FALLBACK_ORDER
        # and pick markdownlint-cli2 just because it was on PATH first.
        runner = _runner_with(Tool.MARKDOWNLINT_CLI2, Tool.PRETTIER)
        self.assertEqual(
            select_tool("/repo/.prettierrc", runner), Tool.PRETTIER,
        )

    def test_subdir_baseline_path_matches_family_preference(self) -> None:
        runner = _runner_with(Tool.MARKDOWNLINT_CLI2, Tool.PRETTIER)
        self.assertEqual(
            select_tool("config/.prettierrc.json", runner), Tool.PRETTIER,
        )

    def test_absolute_markdownlint_baseline_picks_markdownlint(self) -> None:
        runner = _runner_with(Tool.MARKDOWNLINT_CLI2, Tool.PRETTIER)
        self.assertEqual(
            select_tool("/repo/.markdownlint.yaml", runner), Tool.MARKDOWNLINT_CLI2,
        )


class BaselineBelongsToToolTests(unittest.TestCase):
    def test_prettierrc_belongs_to_prettier(self) -> None:
        self.assertTrue(baseline_belongs_to_tool(".prettierrc", Tool.PRETTIER))
        self.assertTrue(baseline_belongs_to_tool(".prettierrc.json", Tool.PRETTIER))
        self.assertTrue(
            baseline_belongs_to_tool("prettier.config.cjs", Tool.PRETTIER),
        )

    def test_markdownlint_baseline_belongs_to_both_clis(self) -> None:
        self.assertTrue(
            baseline_belongs_to_tool(".markdownlint.json", Tool.MARKDOWNLINT_CLI2),
        )
        self.assertTrue(
            baseline_belongs_to_tool(".markdownlint.json", Tool.MARKDOWNLINT),
        )

    def test_mdformat_baseline_belongs_to_mdformat(self) -> None:
        self.assertTrue(baseline_belongs_to_tool(".mdformat.toml", Tool.MDFORMAT))

    def test_cross_family_baseline_does_not_belong(self) -> None:
        # .prettierrc must NOT belong to markdownlint — passing it as
        # --config to markdownlint would either error or be misparsed.
        self.assertFalse(
            baseline_belongs_to_tool(".prettierrc", Tool.MARKDOWNLINT_CLI2),
        )
        self.assertFalse(baseline_belongs_to_tool(".markdownlint.json", Tool.PRETTIER))

    def test_editorconfig_belongs_to_no_tool(self) -> None:
        for tool in Tool:
            self.assertFalse(baseline_belongs_to_tool(".editorconfig", tool))

    def test_universal_subset_belongs_to_no_tool(self) -> None:
        for tool in Tool:
            self.assertFalse(baseline_belongs_to_tool("universal-subset", tool))

    def test_absolute_path_resolves_via_basename(self) -> None:
        # /repo/.prettierrc must answer the same as bare .prettierrc.
        self.assertTrue(
            baseline_belongs_to_tool("/repo/.prettierrc", Tool.PRETTIER),
        )


if __name__ == "__main__":
    unittest.main()
