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

    def test_markdownlint_cli2_config_falls_back_when_only_legacy_cli_available(self) -> None:
        # `.markdownlint-cli2.jsonc` baseline must NOT route to the legacy
        # markdownlint binary even when that's the only markdownlint-
        # family CLI on PATH — the file format is cli2-specific. Selection
        # falls through to FALLBACK_ORDER instead. markdownlint may still
        # end up selected via the fallback chain (it's in FALLBACK_ORDER),
        # but baseline_belongs_to_tool will then say False, so run_tool
        # skips the --config forward and the legacy CLI runs via its own
        # discovery (likely with no config — safer than mis-parsing).
        runner = _runner_with(Tool.MARKDOWNLINT)
        # The fallback selects markdownlint (it's in FALLBACK_ORDER and
        # is the only tool present), but that's OK because the runner
        # won't forward the cli2 config to it.
        self.assertEqual(
            select_tool(".markdownlint-cli2.jsonc", runner), Tool.MARKDOWNLINT,
        )

    def test_windows_style_baseline_selects_family_under_posix(self) -> None:
        # Regression: a Windows-style --baseline path supplied to a POSIX
        # Python (WSL / Git Bash / CI runner that accepts Windows paths)
        # used to skip the family-prefix match because os.path.basename
        # didn't split on backslashes, falling through to FALLBACK_ORDER
        # and selecting whichever formatter happened to be on PATH first.
        # With backslashes normalized, the family preference wins.
        runner = _runner_with(Tool.MARKDOWNLINT_CLI2, Tool.PRETTIER)
        self.assertEqual(
            select_tool("C:\\repo\\.prettierrc", runner), Tool.PRETTIER,
        )

    def test_markdownlint_cli2_config_picks_cli2_when_available(self) -> None:
        # When CLI2 IS on PATH, the cli2-specific baseline routes there
        # directly via the dedicated `.markdownlint-cli2.` prefix.
        runner = _runner_with(Tool.MARKDOWNLINT_CLI2, Tool.MARKDOWNLINT, Tool.PRETTIER)
        self.assertEqual(
            select_tool(".markdownlint-cli2.jsonc", runner), Tool.MARKDOWNLINT_CLI2,
        )

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

    def test_markdownlint_cli2_config_belongs_only_to_cli2(self) -> None:
        # `.markdownlint-cli2.jsonc` is a cli2-specific format the legacy
        # markdownlint binary can't parse. Routing the cli2 baseline to
        # Tool.MARKDOWNLINT (via the broader `.markdownlint.` prefix)
        # would cause run_tool to forward the cli2 config as --config to
        # the wrong CLI.
        self.assertTrue(
            baseline_belongs_to_tool(".markdownlint-cli2.jsonc", Tool.MARKDOWNLINT_CLI2),
        )
        self.assertFalse(
            baseline_belongs_to_tool(".markdownlint-cli2.jsonc", Tool.MARKDOWNLINT),
        )
        self.assertTrue(
            baseline_belongs_to_tool(".markdownlint-cli2.yaml", Tool.MARKDOWNLINT_CLI2),
        )
        self.assertFalse(
            baseline_belongs_to_tool(".markdownlint-cli2.yaml", Tool.MARKDOWNLINT),
        )

    def test_windows_style_baseline_path_belongs_under_posix(self) -> None:
        # Regression: os.path.basename on POSIX doesn't split on
        # backslashes, so a Windows-style --baseline C:\\repo\\.prettierrc
        # supplied under WSL / Git Bash / POSIX Python returned the
        # entire string from basename, the family-prefix match failed,
        # and baseline_belongs_to_tool reported False — the runner then
        # skipped --config forwarding. Backslashes are now normalized
        # to forward slashes before basename, so the helper gives the
        # right answer on every host.
        self.assertTrue(
            baseline_belongs_to_tool("C:\\repo\\.prettierrc", Tool.PRETTIER),
        )
        self.assertTrue(
            baseline_belongs_to_tool(
                "C:\\repo\\.markdownlint.json", Tool.MARKDOWNLINT_CLI2,
            ),
        )
        self.assertTrue(
            baseline_belongs_to_tool(
                "C:\\repo\\.markdownlint-cli2.jsonc", Tool.MARKDOWNLINT_CLI2,
            ),
        )
        # And cross-family still says False — the normalization doesn't
        # weaken the family discipline.
        self.assertFalse(
            baseline_belongs_to_tool(
                "C:\\repo\\.markdownlint-cli2.jsonc", Tool.MARKDOWNLINT,
            ),
        )

    def test_markdownlint_rule_config_belongs_to_both_clis(self) -> None:
        # `.markdownlint.json` is the shared rule-config format; either
        # binary can consume it. Both must report True.
        for name in (
            ".markdownlint.json",
            ".markdownlint.jsonc",
            ".markdownlint.yaml",
            ".markdownlint.yml",
        ):
            self.assertTrue(
                baseline_belongs_to_tool(name, Tool.MARKDOWNLINT_CLI2),
                name,
            )
            self.assertTrue(
                baseline_belongs_to_tool(name, Tool.MARKDOWNLINT),
                name,
            )


if __name__ == "__main__":
    unittest.main()
