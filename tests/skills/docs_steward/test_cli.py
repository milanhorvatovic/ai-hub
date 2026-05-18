"""cli.main — end-to-end through serialization, with patched runner."""

from __future__ import annotations

import io
import json
import unittest
from unittest.mock import patch

from docs_steward.cli import (
    _resolve_against_root,
    _resolve_config_against_root,
    main,
)
from docs_steward.process import ProcessResult

from .fakes import FakeProcessRunner


class CliEndToEndTests(unittest.TestCase):
    def _run(self, runner: FakeProcessRunner, argv: list[str]) -> tuple[int, list[dict]]:
        buf = io.StringIO()
        with patch("docs_steward.cli.SubprocessRunner", return_value=runner), patch(
            "sys.stdout", buf
        ):
            code = main(argv)
        lines = [line for line in buf.getvalue().splitlines() if line.strip()]
        return code, [json.loads(line) for line in lines]

    def test_probe_no_tools_emits_one_missing_event_exit_3(self) -> None:
        code, events = self._run(FakeProcessRunner(), ["probe"])
        self.assertEqual(code, 3)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["event"], "missing")

    def test_recommend_tools_no_tools_yields_6_recommends(self) -> None:
        code, events = self._run(FakeProcessRunner(), ["recommend-tools"])
        self.assertEqual(code, 1)
        recommends = [e for e in events if e["event"] == "recommend"]
        self.assertEqual(len(recommends), 6)
        self.assertEqual([r["detail"]["priority_rank"] for r in recommends], [1, 2, 3, 4, 5, 6])

    def test_audit_baseline_override_skips_detection(self) -> None:
        cmd = ("prettier", "--check", "--parser", "markdown", "**/*.md")
        runner = FakeProcessRunner(
            paths={"prettier": "/x/prettier", "git": "/x/git"},
            results={
                ("git", "rev-parse", "--show-toplevel"): ProcessResult(
                    0, "/repo\n", ""
                ),
                cmd: ProcessResult(0, "", ""),
            },
        )
        code, events = self._run(runner, ["md-audit", "--baseline", ".prettierrc"])
        self.assertEqual(code, 0)
        selected = [e for e in events if e["event"] == "selected"][0]
        self.assertEqual(selected["detail"]["baseline"], ".prettierrc")

    def test_format_with_unwrap_propagates_flag_through_to_command(self) -> None:
        cmd = (
            "prettier",
            "--prose-wrap=never",
            "--write",
            "--parser",
            "markdown",
            "**/*.md",
        )
        runner = FakeProcessRunner(
            paths={"prettier": "/x/prettier", "git": "/x/git"},
            results={
                ("git", "rev-parse", "--show-toplevel"): ProcessResult(0, "/repo\n", ""),
                cmd: ProcessResult(0, "foo.md 12ms\n", ""),
            },
        )
        code, events = self._run(
            runner, ["md-format", "--baseline", ".prettierrc", "--unwrap"]
        )
        self.assertEqual(code, 1)
        selected = [e for e in events if e["event"] == "selected"][0]
        self.assertTrue(selected["detail"]["unwrap"])
        self.assertIn("--prose-wrap=never", selected["detail"]["cmd"])

    def test_unknown_subcommand_exits_2(self) -> None:
        with self.assertRaises(SystemExit) as ctx, patch("sys.stderr", io.StringIO()):
            main(["bogus"])
        self.assertEqual(ctx.exception.code, 2)

    def test_md_audit_accepts_positional_files(self) -> None:
        # Per-file targeting (#1) via positional args.
        cmd = ("prettier", "--check", "--parser", "markdown", "docs/intro.md")
        runner = FakeProcessRunner(
            paths={"prettier": "/x/prettier", "git": "/x/git"},
            results={
                ("git", "rev-parse", "--show-toplevel"): ProcessResult(0, "/repo\n", ""),
                cmd: ProcessResult(0, "", ""),
            },
        )
        code, events = self._run(
            runner, ["md-audit", "--baseline", ".prettierrc", "docs/intro.md"],
        )
        self.assertEqual(code, 0)
        selected = [e for e in events if e["event"] == "selected"][0]
        self.assertEqual(selected["detail"]["files_scoped"], 1)

    def test_md_audit_quiet_filters_preamble(self) -> None:
        cmd = ("prettier", "--check", "--parser", "markdown", "**/*.md")
        runner = FakeProcessRunner(
            paths={"prettier": "/x/prettier", "git": "/x/git"},
            results={
                ("git", "rev-parse", "--show-toplevel"): ProcessResult(0, "/repo\n", ""),
                cmd: ProcessResult(
                    1, "Linting: 3 file(s)\nSummary: 1 error(s)\nfoo.md:1 MD040\n", "",
                ),
            },
        )
        code, events = self._run(
            runner, ["md-audit", "--baseline", ".prettierrc", "--quiet"],
        )
        self.assertEqual(code, 1)
        findings = [e for e in events if e["event"] == "finding"]
        self.assertEqual(len(findings), 1)
        self.assertIn("MD040", findings[0]["detail"])

    def test_md_format_dry_run_emits_would_change(self) -> None:
        audit_cmd = ("prettier", "--check", "--parser", "markdown", "**/*.md")
        runner = FakeProcessRunner(
            paths={"prettier": "/x/prettier", "git": "/x/git"},
            results={
                ("git", "rev-parse", "--show-toplevel"): ProcessResult(0, "/repo\n", ""),
                audit_cmd: ProcessResult(1, "foo.md\n", ""),
            },
        )
        code, events = self._run(
            runner, ["md-format", "--baseline", ".prettierrc", "--dry-run"],
        )
        self.assertEqual(code, 1)
        self.assertEqual(
            [e for e in events if e["event"] == "would-change"],
            [{"event": "would-change", "tool": "prettier", "detail": "foo.md"}],
        )

    def test_md_audit_emits_plugin_missing_when_mdformat_lacks_gfm(self) -> None:
        # mdformat selected, mdformat-gfm not installed, file has GFM table.
        # The audit should emit a plugin-missing event before the formatter runs.
        # Use --baseline that maps to mdformat (no markdownlint/prettier on PATH).
        import os
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            md_path = os.path.join(tmp, "table.md")
            with open(md_path, "w", encoding="utf-8") as fh:
                fh.write("| col | col |\n|---|---|\n| a | b |\n")

            audit_cmd = ("mdformat", "--check", md_path)
            runner = FakeProcessRunner(
                paths={"mdformat": "/x/mdformat", "git": "/x/git"},
                results={
                    ("git", "rev-parse", "--show-toplevel"): ProcessResult(0, tmp + "\n", ""),
                    audit_cmd: ProcessResult(0, "", ""),
                },
            )
            code, events = self._run(
                runner, ["md-audit", "--baseline", "universal-subset", md_path],
            )
            self.assertEqual(code, 0)
            plugin_missing = [e for e in events if e["event"] == "plugin-missing"]
            self.assertEqual(len(plugin_missing), 1)
            self.assertEqual(plugin_missing[0]["detail"]["plugin"], "gfm")
            self.assertEqual(plugin_missing[0]["detail"]["file"], md_path)

    def test_md_audit_plugin_missing_resolves_relative_files_against_root(self) -> None:
        # Same setup as the previous test, but the positional file argument
        # is relative ("table.md") and the process CWD is intentionally
        # unrelated. Without resolution the read would fail and no
        # plugin-missing event would be emitted; with resolution the read
        # hits <root>/table.md and the event fires.
        import os
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            md_path = os.path.join(tmp, "table.md")
            with open(md_path, "w", encoding="utf-8") as fh:
                fh.write("| col | col |\n|---|---|\n| a | b |\n")

            # The formatter receives the relative path verbatim (cwd=root).
            audit_cmd = ("mdformat", "--check", "table.md")
            runner = FakeProcessRunner(
                paths={"mdformat": "/x/mdformat", "git": "/x/git"},
                results={
                    ("git", "rev-parse", "--show-toplevel"): ProcessResult(0, tmp + "\n", ""),
                    audit_cmd: ProcessResult(0, "", ""),
                },
            )
            code, events = self._run(
                runner, ["md-audit", "--baseline", "universal-subset", "table.md"],
            )
            self.assertEqual(code, 0)
            plugin_missing = [e for e in events if e["event"] == "plugin-missing"]
            self.assertEqual(len(plugin_missing), 1)
            self.assertEqual(plugin_missing[0]["detail"]["plugin"], "gfm")
            # Event records the resolved (absolute) path so consumers can
            # locate the file regardless of where the CLI was invoked from.
            self.assertEqual(plugin_missing[0]["detail"]["file"], md_path)

    def test_md_audit_skips_plugin_check_when_tool_is_not_mdformat(self) -> None:
        # prettier selected → no plugin-missing event regardless of file content.
        cmd = ("prettier", "--check", "--parser", "markdown", "**/*.md")
        runner = FakeProcessRunner(
            paths={"prettier": "/x/prettier", "git": "/x/git"},
            results={
                ("git", "rev-parse", "--show-toplevel"): ProcessResult(0, "/repo\n", ""),
                cmd: ProcessResult(0, "", ""),
            },
        )
        code, events = self._run(runner, ["md-audit", "--baseline", ".prettierrc"])
        self.assertEqual(code, 0)
        self.assertEqual([e for e in events if e["event"] == "plugin-missing"], [])

    def test_md_fix_clean_yields_zero_delta(self) -> None:
        audit_cmd = ("prettier", "--check", "--parser", "markdown", "**/*.md")
        runner = FakeProcessRunner(
            paths={"prettier": "/x/prettier", "git": "/x/git"},
            results={
                ("git", "rev-parse", "--show-toplevel"): ProcessResult(0, "/repo\n", ""),
                audit_cmd: ProcessResult(0, "", ""),
            },
        )
        code, events = self._run(
            runner, ["md-fix", "--baseline", ".prettierrc"],
        )
        self.assertEqual(code, 0)
        deltas = [e for e in events if e["event"] == "delta"]
        self.assertEqual(len(deltas), 1)
        self.assertEqual(
            deltas[0]["detail"], {"resolved": 0, "still_open": 0, "new": 0},
        )


class ResolveAgainstRootTests(unittest.TestCase):
    def test_absolute_paths_pass_through(self) -> None:
        resolved = _resolve_against_root(("/repo/a.md", "/repo/b.md"), "/somewhere/else")
        self.assertEqual(resolved, ("/repo/a.md", "/repo/b.md"))

    def test_relative_paths_joined_to_root(self) -> None:
        import os
        resolved = _resolve_against_root(("docs/a.md", "b.md"), "/repo")
        self.assertEqual(
            resolved,
            (os.path.join("/repo", "docs/a.md"), os.path.join("/repo", "b.md")),
        )

    def test_mixed_paths(self) -> None:
        import os
        resolved = _resolve_against_root(("/abs/a.md", "rel/b.md"), "/repo")
        self.assertEqual(resolved, ("/abs/a.md", os.path.join("/repo", "rel/b.md")))

    def test_empty_files_returns_empty_tuple(self) -> None:
        self.assertEqual(_resolve_against_root((), "/repo"), ())


class ResolveConfigAgainstRootTests(unittest.TestCase):
    def test_none_passes_through(self) -> None:
        # None signals "use the bundled fallback" — must NOT be rewritten
        # to a path under root, or audit_frontmatter would receive a fake
        # path instead of routing through bundled_config_for().
        self.assertIsNone(_resolve_config_against_root(None, "/repo"))

    def test_absolute_path_passes_through(self) -> None:
        self.assertEqual(
            _resolve_config_against_root("/etc/yamllint.yaml", "/repo"),
            "/etc/yamllint.yaml",
        )

    def test_relative_path_joined_to_root(self) -> None:
        import os
        self.assertEqual(
            _resolve_config_against_root(".yamllint", "/repo"),
            os.path.join("/repo", ".yamllint"),
        )

    def test_relative_path_with_subdir_joined_to_root(self) -> None:
        import os
        self.assertEqual(
            _resolve_config_against_root("config/.yamllint.yaml", "/repo"),
            os.path.join("/repo", "config/.yamllint.yaml"),
        )


if __name__ == "__main__":
    unittest.main()
