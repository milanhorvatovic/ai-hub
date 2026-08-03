"""baseline.detect_baselines — all-matches discovery in declaration order."""

from __future__ import annotations

import unittest

from docs_steward.baseline import (
    BASELINE_CANDIDATES,
    detect_baselines,
)

from .fakes import FakeFileSystem

ROOT = "/repo"


class DetectBaselinesTests(unittest.TestCase):
    def test_empty_fs_returns_empty_tuple(self) -> None:
        self.assertEqual(detect_baselines(FakeFileSystem(), ROOT), ())

    def test_single_match_returns_that_candidate(self) -> None:
        fs = FakeFileSystem(files={f"{ROOT}/.prettierrc": ""})
        self.assertEqual(detect_baselines(fs, ROOT), (".prettierrc",))

    def test_all_matches_returned_in_declaration_order(self) -> None:
        # The full detected set is the plan builder's raw material — a
        # lint config must not hide a formatter config (or vice versa).
        fs = FakeFileSystem(
            files={
                f"{ROOT}/.prettierrc": "",
                f"{ROOT}/.markdownlint.json": "",
            }
        )
        self.assertEqual(
            detect_baselines(fs, ROOT), (".markdownlint.json", ".prettierrc")
        )

    def test_candidate_list_is_non_empty_and_unique(self) -> None:
        self.assertGreater(len(BASELINE_CANDIDATES), 0)
        self.assertEqual(len(BASELINE_CANDIDATES), len(set(BASELINE_CANDIDATES)))

    def test_dprint_precedes_editorconfig(self) -> None:
        # Per SKILL.md step 3 (after round 8): dprint.json — a formatter-
        # specific config with a real selector preference — ranks above
        # the generic .editorconfig style hint, so declaration order gives
        # the formatter concern to dprint when a repo declares both.
        idx_dprint = BASELINE_CANDIDATES.index("dprint.json")
        idx_editorconfig = BASELINE_CANDIDATES.index(".editorconfig")
        self.assertLess(idx_dprint, idx_editorconfig)

    def test_declaration_order_ranks_mdformat_dprint_editorconfig(self) -> None:
        # Per SKILL.md section 3: .mdformat.toml before dprint.json before
        # .editorconfig. Declaration order is the same-kind precedence
        # policy — the first formatter-family config owns the concern.
        fs = FakeFileSystem(
            files={
                f"{ROOT}/.mdformat.toml": "",
                f"{ROOT}/.editorconfig": "",
                f"{ROOT}/dprint.json": "",
            }
        )
        self.assertEqual(
            detect_baselines(fs, ROOT),
            (".mdformat.toml", "dprint.json", ".editorconfig"),
        )


if __name__ == "__main__":
    unittest.main()
