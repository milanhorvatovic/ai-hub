"""runner.run_tool + run_fix_cycle — orchestration + exit-code contract."""

from __future__ import annotations

import unittest

from docs_steward.baseline import UNIVERSAL_SUBSET
from docs_steward.events import EventType
from docs_steward.modes import Mode
from docs_steward.process import ProcessResult
from docs_steward.runner import run_fix_cycle, run_tool
from docs_steward.tools import Tool

from .fakes import FakeProcessRunner


ROOT = "/repo"


class RunToolTests(unittest.TestCase):
    def test_no_usable_tool_returns_exit_3(self) -> None:
        events, code = run_tool(Mode.AUDIT, UNIVERSAL_SUBSET, False, FakeProcessRunner(), ROOT)
        self.assertEqual(code, 3)
        self.assertEqual(events[0].event, EventType.MISSING)

    def test_clean_audit_returns_exit_0(self) -> None:
        cmd = ("prettier", "--check", "--parser", "markdown", "**/*.md")
        runner = FakeProcessRunner(
            paths={"prettier": "/x/prettier"},
            results={cmd: ProcessResult(0, "", "")},
        )
        events, code = run_tool(Mode.AUDIT, ".prettierrc", False, runner, ROOT)
        self.assertEqual(code, 0)
        kinds = [e.event for e in events]
        self.assertIn(EventType.SELECTED, kinds)
        self.assertIn(EventType.CLEAN, kinds)

    def test_audit_clean_with_preamble_stdout_returns_exit_0(self) -> None:
        # Regression: markdownlint-cli2 prints version + file count + "Summary: 0 error(s)"
        # on stdout even when clean. Trust returncode in AUDIT mode; do not emit the
        # preamble lines as `finding` events nor flip the exit code to 1.
        cmd = ("prettier", "--check", "--parser", "markdown", "**/*.md")
        preamble = "prettier v3.8.3\nLinting: 3 file(s)\nSummary: 0 error(s)\n"
        runner = FakeProcessRunner(
            paths={"prettier": "/x/prettier"},
            results={cmd: ProcessResult(0, preamble, "")},
        )
        events, code = run_tool(Mode.AUDIT, ".prettierrc", False, runner, ROOT)
        self.assertEqual(code, 0)
        findings = [e for e in events if e.event == EventType.FINDING]
        self.assertEqual(findings, [])
        self.assertIn(EventType.CLEAN, [e.event for e in events])

    def test_findings_emit_finding_events_exit_1(self) -> None:
        cmd = ("prettier", "--check", "--parser", "markdown", "**/*.md")
        runner = FakeProcessRunner(
            paths={"prettier": "/x/prettier"},
            results={cmd: ProcessResult(1, "Code style issues found in foo.md\n", "")},
        )
        events, code = run_tool(Mode.AUDIT, ".prettierrc", False, runner, ROOT)
        self.assertEqual(code, 1)
        findings = [e for e in events if e.event == EventType.FINDING]
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].detail, "Code style issues found in foo.md")

    def test_tool_error_exit_geq_2_emits_error_event_and_exit_2(self) -> None:
        cmd = ("prettier", "--check", "--parser", "markdown", "**/*.md")
        runner = FakeProcessRunner(
            paths={"prettier": "/x/prettier"},
            results={cmd: ProcessResult(2, "", "config error")},
        )
        events, code = run_tool(Mode.AUDIT, ".prettierrc", False, runner, ROOT)
        self.assertEqual(code, 2)
        errors = [e for e in events if e.event == EventType.ERROR]
        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0].detail, {"exit": 2})

    def test_format_mode_emits_changed_not_finding(self) -> None:
        cmd = ("prettier", "--write", "--parser", "markdown", "**/*.md")
        runner = FakeProcessRunner(
            paths={"prettier": "/x/prettier"},
            results={cmd: ProcessResult(0, "foo.md 12ms\n", "")},
        )
        events, code = run_tool(Mode.FORMAT, ".prettierrc", False, runner, ROOT)
        self.assertEqual(code, 1)
        self.assertEqual(
            [e for e in events if e.event == EventType.CHANGED][0].detail,
            "foo.md 12ms",
        )

    def test_universal_subset_with_bundled_config_emits_bundled_event(self) -> None:
        # Selector with no baseline preference + only prettier on PATH falls
        # back to prettier; bundled config applies.
        from docs_steward.bundled_config import bundled_config_for
        cfg = bundled_config_for(Tool.PRETTIER)
        assert cfg is not None
        cmd = (
            "prettier",
            "--config",
            cfg,
            "--check",
            "--parser",
            "markdown",
            "**/*.md",
        )
        runner = FakeProcessRunner(
            paths={"prettier": "/x/prettier"},
            results={cmd: ProcessResult(0, "", "")},
        )
        events, code = run_tool(Mode.AUDIT, UNIVERSAL_SUBSET, False, runner, ROOT)
        self.assertEqual(code, 0)
        bundled = [e for e in events if e.event == EventType.BUNDLED_CONFIG]
        self.assertEqual(len(bundled), 1)
        self.assertEqual(bundled[0].detail, cfg)
        selected = [e for e in events if e.event == EventType.SELECTED][0]
        self.assertEqual(selected.detail["config_source"], "bundled")  # type: ignore[index]

    def test_universal_subset_unsupported_tool_uses_tool_default(self) -> None:
        # Force selection of mdformat (no bundled config) via universal-subset
        # with only mdformat on PATH.
        cmd = ("mdformat", "--check", ".")
        runner = FakeProcessRunner(
            paths={"mdformat": "/x/mdformat"},
            results={cmd: ProcessResult(0, "", "")},
        )
        events, code = run_tool(Mode.AUDIT, UNIVERSAL_SUBSET, False, runner, ROOT)
        self.assertEqual(code, 0)
        bundled = [e for e in events if e.event == EventType.BUNDLED_CONFIG]
        self.assertEqual(len(bundled), 0)
        selected = [e for e in events if e.event == EventType.SELECTED][0]
        self.assertEqual(selected.detail["config_source"], "tool-default")  # type: ignore[index]

    def test_unwrap_flag_propagates_to_command(self) -> None:
        cmd = (
            "prettier",
            "--prose-wrap=never",
            "--check",
            "--parser",
            "markdown",
            "**/*.md",
        )
        runner = FakeProcessRunner(
            paths={"prettier": "/x/prettier"},
            results={cmd: ProcessResult(0, "", "")},
        )
        _, code = run_tool(Mode.AUDIT, ".prettierrc", True, runner, ROOT)
        self.assertEqual(code, 0)

    def test_cr_lines_are_stripped(self) -> None:
        cmd = ("prettier", "--check", "--parser", "markdown", "**/*.md")
        runner = FakeProcessRunner(
            paths={"prettier": "/x/prettier"},
            results={cmd: ProcessResult(1, "foo.md\r\nbar.md\r\n", "")},
        )
        events, _ = run_tool(Mode.AUDIT, ".prettierrc", False, runner, ROOT)
        findings = [e.detail for e in events if e.event == EventType.FINDING]
        self.assertEqual(findings, ["foo.md", "bar.md"])


# ============================================================
# Per-file targeting (#1)
# ============================================================

class PerFileTargetingTests(unittest.TestCase):
    def test_explicit_files_replace_glob_in_cmd(self) -> None:
        # When files= is passed, the glob "**/*.md" + #node_modules etc. are
        # dropped and replaced with the explicit list.
        cmd = ("prettier", "--check", "--parser", "markdown", "docs/intro.md", "README.md")
        runner = FakeProcessRunner(
            paths={"prettier": "/x/prettier"},
            results={cmd: ProcessResult(0, "", "")},
        )
        events, code = run_tool(
            Mode.AUDIT, ".prettierrc", False, runner, ROOT,
            files=["docs/intro.md", "README.md"],
        )
        self.assertEqual(code, 0)
        selected = [e for e in events if e.event == EventType.SELECTED][0]
        self.assertEqual(selected.detail["files_scoped"], 2)  # type: ignore[index]

    def test_no_files_keeps_default_glob(self) -> None:
        cmd = ("prettier", "--check", "--parser", "markdown", "**/*.md")
        runner = FakeProcessRunner(
            paths={"prettier": "/x/prettier"},
            results={cmd: ProcessResult(0, "", "")},
        )
        events, code = run_tool(Mode.AUDIT, ".prettierrc", False, runner, ROOT)
        self.assertEqual(code, 0)
        selected = [e for e in events if e.event == EventType.SELECTED][0]
        self.assertIsNone(selected.detail["files_scoped"])  # type: ignore[index]

    def test_markdownlint_cli2_drops_negative_globs_when_scoped(self) -> None:
        # markdownlint-cli2 default cmd includes #node_modules etc. — should
        # all be dropped when explicit files are provided. baseline is the
        # repo's .markdownlint.json so no bundled --config is added.
        cmd = ("markdownlint-cli2", "/repo/foo.md")
        runner = FakeProcessRunner(
            paths={"markdownlint-cli2": "/x/markdownlint-cli2"},
            results={cmd: ProcessResult(0, "", "")},
        )
        events, code = run_tool(
            Mode.AUDIT, ".markdownlint.json", False, runner, ROOT,
            files=["/repo/foo.md"],
        )
        self.assertEqual(code, 0)
        selected = [e for e in events if e.event == EventType.SELECTED][0]
        self.assertIn("/repo/foo.md", selected.detail["cmd"])  # type: ignore[index]
        # Negative-glob tokens must be absent under scoping.
        self.assertNotIn("#node_modules", selected.detail["cmd"])  # type: ignore[index]
        self.assertNotIn("**/*.md", selected.detail["cmd"])  # type: ignore[index]


# ============================================================
# --quiet flag (#6)
# ============================================================

class QuietFlagTests(unittest.TestCase):
    def test_quiet_drops_markdownlint_cli2_preamble(self) -> None:
        cmd = ("prettier", "--check", "--parser", "markdown", "**/*.md")
        # Mixed preamble + real findings; quiet should drop preamble only.
        output = (
            "Finding: **/*.md\n"
            "Linting: 3 file(s)\n"
            "Summary: 2 error(s)\n"
            "foo.md:1 MD040 fenced-code-language\n"
            "bar.md:7 MD009 trailing-whitespace\n"
        )
        runner = FakeProcessRunner(
            paths={"prettier": "/x/prettier"},
            results={cmd: ProcessResult(1, output, "")},
        )
        events, code = run_tool(
            Mode.AUDIT, ".prettierrc", False, runner, ROOT, quiet=True,
        )
        self.assertEqual(code, 1)
        findings = [e.detail for e in events if e.event == EventType.FINDING]
        # 2 real findings; the 3 preamble lines filtered out.
        self.assertEqual(len(findings), 2)
        self.assertTrue(all("MD0" in f for f in findings))

    def test_not_quiet_keeps_everything(self) -> None:
        cmd = ("prettier", "--check", "--parser", "markdown", "**/*.md")
        output = "Linting: 3 file(s)\nfoo.md:1 MD040 issue\n"
        runner = FakeProcessRunner(
            paths={"prettier": "/x/prettier"},
            results={cmd: ProcessResult(1, output, "")},
        )
        events, _ = run_tool(
            Mode.AUDIT, ".prettierrc", False, runner, ROOT, quiet=False,
        )
        findings = [e for e in events if e.event == EventType.FINDING]
        self.assertEqual(len(findings), 2)  # preamble + finding both kept


# ============================================================
# --dry-run for md-format (#8)
# ============================================================

class DryRunTests(unittest.TestCase):
    def test_dry_run_format_emits_would_change_events(self) -> None:
        # Dry-run swaps to the AUDIT-mode invocation (--check), but emits
        # WOULD_CHANGE events instead of FINDING events.
        audit_cmd = ("prettier", "--check", "--parser", "markdown", "**/*.md")
        runner = FakeProcessRunner(
            paths={"prettier": "/x/prettier"},
            results={audit_cmd: ProcessResult(1, "foo.md\nbar.md\n", "")},
        )
        events, code = run_tool(
            Mode.FORMAT, ".prettierrc", False, runner, ROOT, dry_run=True,
        )
        self.assertEqual(code, 1)
        would = [e for e in events if e.event == EventType.WOULD_CHANGE]
        self.assertEqual(len(would), 2)
        # No CHANGED events should fire.
        self.assertEqual([e for e in events if e.event == EventType.CHANGED], [])
        # SELECTED event should record dry_run=True.
        selected = [e for e in events if e.event == EventType.SELECTED][0]
        self.assertTrue(selected.detail["dry_run"])  # type: ignore[index]

    def test_dry_run_format_clean_yields_no_would_change(self) -> None:
        audit_cmd = ("prettier", "--check", "--parser", "markdown", "**/*.md")
        runner = FakeProcessRunner(
            paths={"prettier": "/x/prettier"},
            results={audit_cmd: ProcessResult(0, "", "")},
        )
        events, code = run_tool(
            Mode.FORMAT, ".prettierrc", False, runner, ROOT, dry_run=True,
        )
        self.assertEqual(code, 0)
        self.assertEqual([e for e in events if e.event == EventType.WOULD_CHANGE], [])
        self.assertIn(EventType.CLEAN, [e.event for e in events])


# ============================================================
# run_fix_cycle (#4)
# ============================================================

class RunFixCycleTests(unittest.TestCase):
    def test_clean_pre_audit_skips_format_emits_zero_delta(self) -> None:
        audit_cmd = ("prettier", "--check", "--parser", "markdown", "**/*.md")
        runner = FakeProcessRunner(
            paths={"prettier": "/x/prettier"},
            results={audit_cmd: ProcessResult(0, "", "")},
        )
        events, code = run_fix_cycle(runner, ROOT, ".prettierrc", False)
        self.assertEqual(code, 0)
        deltas = [e for e in events if e.event == EventType.DELTA]
        self.assertEqual(len(deltas), 1)
        self.assertEqual(
            deltas[0].detail,
            {"resolved": 0, "still_open": 0, "new": 0},
        )

    def test_findings_then_format_then_re_audit_clean_emits_resolved(self) -> None:
        audit_cmd = ("prettier", "--check", "--parser", "markdown", "**/*.md")
        fmt_cmd = ("prettier", "--write", "--parser", "markdown", "**/*.md")
        # Pre-audit finds 2 issues; format succeeds; post-audit is clean.
        results = {
            audit_cmd: ProcessResult(1, "foo.md:1 MD040\nbar.md:5 MD009\n", ""),
            fmt_cmd: ProcessResult(0, "foo.md 12ms\nbar.md 8ms\n", ""),
        }
        # First and third calls to audit_cmd return findings, clean respectively.
        # FakeProcessRunner returns the same result for the same key. Need a
        # stateful runner. Build it inline.
        call_count = {"audit": 0}

        original_run = FakeProcessRunner(paths={"prettier": "/x/prettier"}, results=results).run

        class StatefulRunner(FakeProcessRunner):
            def run(self, args, cwd=None, stdin=None):  # type: ignore[override]
                key = tuple(args)
                if key == audit_cmd:
                    call_count["audit"] += 1
                    if call_count["audit"] == 2:
                        return ProcessResult(0, "", "")
                return original_run(args, cwd, stdin)

        runner = StatefulRunner(paths={"prettier": "/x/prettier"}, results=results)
        events, code = run_fix_cycle(runner, ROOT, ".prettierrc", False)
        self.assertEqual(code, 0)
        deltas = [e for e in events if e.event == EventType.DELTA]
        self.assertEqual(len(deltas), 1)
        self.assertEqual(deltas[0].detail["resolved"], 2)  # type: ignore[index]
        self.assertEqual(deltas[0].detail["still_open"], 0)  # type: ignore[index]
        self.assertEqual(deltas[0].detail["new"], 0)  # type: ignore[index]

    def test_audit_error_short_circuits(self) -> None:
        audit_cmd = ("prettier", "--check", "--parser", "markdown", "**/*.md")
        runner = FakeProcessRunner(
            paths={"prettier": "/x/prettier"},
            results={audit_cmd: ProcessResult(2, "", "prettier config error")},
        )
        events, code = run_fix_cycle(runner, ROOT, ".prettierrc", False)
        self.assertEqual(code, 2)
        # No DELTA event since we bailed early.
        self.assertEqual([e for e in events if e.event == EventType.DELTA], [])


if __name__ == "__main__":
    unittest.main()
