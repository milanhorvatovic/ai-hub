"""bundled_config.bundled_config_for — coverage scope + path resolution."""

from __future__ import annotations

import os.path
import unittest

from docs_steward.bundled_config import bundled_config_for
from docs_steward.tools import Tool


class BundledConfigTests(unittest.TestCase):
    def test_markdownlint_cli2_resolves_to_shipped_json(self) -> None:
        path = bundled_config_for(Tool.MARKDOWNLINT_CLI2)
        self.assertIsNotNone(path)
        assert path is not None  # narrow for type checker
        self.assertTrue(path.endswith(os.path.join("assets", "configs", "markdownlint.json")))
        self.assertTrue(os.path.isabs(path))
        self.assertTrue(os.path.isfile(path))

    def test_markdownlint_shares_config_with_cli2(self) -> None:
        self.assertEqual(
            bundled_config_for(Tool.MARKDOWNLINT),
            bundled_config_for(Tool.MARKDOWNLINT_CLI2),
        )

    def test_prettier_resolves_to_shipped_json(self) -> None:
        path = bundled_config_for(Tool.PRETTIER)
        self.assertIsNotNone(path)
        assert path is not None
        self.assertTrue(path.endswith(os.path.join("assets", "configs", "prettierrc.json")))
        self.assertTrue(os.path.isfile(path))

    def test_mdformat_dprint_remark_are_unsupported(self) -> None:
        # See assets/configs/README.md for why these three are intentionally skipped.
        for tool in (Tool.MDFORMAT, Tool.DPRINT, Tool.REMARK):
            with self.subTest(tool=tool):
                self.assertIsNone(bundled_config_for(tool))


if __name__ == "__main__":
    unittest.main()
