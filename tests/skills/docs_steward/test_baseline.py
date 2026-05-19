"""baseline.detect_baseline — first-match precedence + override semantics."""

from __future__ import annotations

import os.path
import unittest

from docs_steward.baseline import (
    BASELINE_CANDIDATES,
    UNIVERSAL_SUBSET,
    detect_baseline,
)

from .fakes import FakeFileSystem


ROOT = "/repo"


class DetectBaselineTests(unittest.TestCase):
    def test_empty_fs_returns_universal_subset(self) -> None:
        self.assertEqual(detect_baseline(FakeFileSystem(), ROOT), UNIVERSAL_SUBSET)

    def test_single_match_returns_that_candidate(self) -> None:
        fs = FakeFileSystem(files={os.path.join(ROOT, ".prettierrc"): ""})
        self.assertEqual(detect_baseline(fs, ROOT), ".prettierrc")

    def test_first_in_declaration_order_wins(self) -> None:
        fs = FakeFileSystem(
            files={
                os.path.join(ROOT, ".prettierrc"): "",
                os.path.join(ROOT, ".markdownlint.json"): "",
            }
        )
        self.assertEqual(detect_baseline(fs, ROOT), ".markdownlint.json")

    def test_override_short_circuits_detection(self) -> None:
        fs = FakeFileSystem(files={os.path.join(ROOT, ".markdownlint.json"): ""})
        self.assertEqual(
            detect_baseline(fs, ROOT, override=".prettierrc"),
            ".prettierrc",
        )

    def test_override_value_not_validated_against_fs(self) -> None:
        """Overrides are intentional — `detect_baseline` does not verify they
        exist. The caller asked for it, the caller gets it."""
        self.assertEqual(
            detect_baseline(FakeFileSystem(), ROOT, override="/does/not/exist"),
            "/does/not/exist",
        )

    def test_candidate_list_is_non_empty_and_unique(self) -> None:
        self.assertGreater(len(BASELINE_CANDIDATES), 0)
        self.assertEqual(len(BASELINE_CANDIDATES), len(set(BASELINE_CANDIDATES)))

    def test_dprint_precedes_editorconfig(self) -> None:
        # Per SKILL.md step 3 (after round 8): dprint.json — a formatter-
        # specific config with a real selector preference — ranks above
        # the generic .editorconfig style hint. A repo declaring both
        # matches dprint, so the selector routes to Tool.DPRINT instead
        # of falling through to FALLBACK_ORDER (which has no preference
        # for .editorconfig).
        idx_dprint = BASELINE_CANDIDATES.index("dprint.json")
        idx_editorconfig = BASELINE_CANDIDATES.index(".editorconfig")
        self.assertLess(idx_dprint, idx_editorconfig)

    def test_dprint_wins_over_editorconfig_when_both_present(self) -> None:
        fs = FakeFileSystem(
            files={
                os.path.join(ROOT, ".editorconfig"): "",
                os.path.join(ROOT, "dprint.json"): "",
            }
        )
        self.assertEqual(detect_baseline(fs, ROOT), "dprint.json")

    def test_mdformat_toml_detected(self) -> None:
        fs = FakeFileSystem(files={os.path.join(ROOT, ".mdformat.toml"): ""})
        self.assertEqual(detect_baseline(fs, ROOT), ".mdformat.toml")

    def test_mdformat_precedes_editorconfig_and_dprint(self) -> None:
        # Per SKILL.md section 3: mdformat is candidate 4, editorconfig 5,
        # dprint 6. When all three are present, .mdformat.toml wins so the
        # selector preference table can route to mdformat instead of
        # falling through to a different formatter on PATH.
        fs = FakeFileSystem(
            files={
                os.path.join(ROOT, ".mdformat.toml"): "",
                os.path.join(ROOT, ".editorconfig"): "",
                os.path.join(ROOT, "dprint.json"): "",
            }
        )
        self.assertEqual(detect_baseline(fs, ROOT), ".mdformat.toml")


if __name__ == "__main__":
    unittest.main()
