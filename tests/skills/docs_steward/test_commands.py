"""commands.build_command — registry-driven argv construction."""

from __future__ import annotations

import unittest

from docs_steward.commands import build_command
from docs_steward.modes import Mode
from docs_steward.tools import REGISTRY, Tool


class BuildCommandTests(unittest.TestCase):
    def test_prettier_audit_no_flags(self) -> None:
        self.assertEqual(
            build_command(Tool.PRETTIER, Mode.AUDIT),
            ["prettier", "--check", "--parser", "markdown", "**/*.md", "**/*.markdown"],
        )

    def test_prettier_format_with_unwrap(self) -> None:
        self.assertEqual(
            build_command(Tool.PRETTIER, Mode.FORMAT, unwrap=True),
            [
                "prettier",
                "--prose-wrap=never",
                "--write",
                "--parser",
                "markdown",
                "**/*.md",
            "**/*.markdown",
            ],
        )

    def test_prettier_with_config_and_unwrap(self) -> None:
        self.assertEqual(
            build_command(
                Tool.PRETTIER, Mode.AUDIT, unwrap=True, config_path="/cfg/prettierrc.json"
            ),
            [
                "prettier",
                "--config",
                "/cfg/prettierrc.json",
                "--prose-wrap=never",
                "--check",
                "--parser",
                "markdown",
                "**/*.md",
            "**/*.markdown",
            ],
        )

    def test_markdownlint_cli2_config_uses_separate_args(self) -> None:
        # Regression guard: markdownlint-cli2 rejects --config=PATH and treats
        # it as a file glob. Must be emitted as two separate argv elements.
        cmd = build_command(
            Tool.MARKDOWNLINT_CLI2, Mode.AUDIT, config_path="/cfg/markdownlint.json"
        )
        idx = cmd.index("--config")
        self.assertEqual(cmd[idx + 1], "/cfg/markdownlint.json")
        # Ensure no combined-form leaked anywhere.
        for part in cmd:
            self.assertFalse(part.startswith("--config="), f"combined form leaked: {part!r}")

    def test_mdformat_unwrap_flag_supported_but_no_config_flag(self) -> None:
        # mdformat has --wrap=no but no --config=PATH equivalent.
        self.assertEqual(
            build_command(
                Tool.MDFORMAT, Mode.FORMAT, unwrap=True, config_path="/ignored"
            ),
            ["mdformat", "--wrap=no", "."],
        )

    def test_dprint_ignores_both_optional_flags(self) -> None:
        self.assertEqual(
            build_command(Tool.DPRINT, Mode.AUDIT, unwrap=True, config_path="/x"),
            ["dprint", "check"],
        )

    def test_markdownlint_cli2_format_includes_fix(self) -> None:
        cmd = build_command(Tool.MARKDOWNLINT_CLI2, Mode.FORMAT)
        self.assertEqual(cmd[0], "markdownlint-cli2")
        self.assertIn("--fix", cmd)
        self.assertIn("**/*.md", cmd)
        self.assertIn("#node_modules", cmd)

    def test_unknown_tool_raises_keyerror(self) -> None:
        with self.assertRaises(KeyError):
            build_command("not-a-tool", Mode.AUDIT)  # type: ignore[arg-type]

    def test_every_registered_tool_builds_both_modes(self) -> None:
        for tool in REGISTRY:
            for mode in (Mode.AUDIT, Mode.FORMAT):
                with self.subTest(tool=tool, mode=mode):
                    cmd = build_command(tool, mode)
                    self.assertEqual(cmd[0], tool.value)
                    self.assertGreater(len(cmd), 0)


if __name__ == "__main__":
    unittest.main()
