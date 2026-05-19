"""yaml_audit.audit_frontmatter — orchestration, output parsing, exit codes."""

from __future__ import annotations

import unittest

from docs_steward.bundled_config import bundled_config_for
from docs_steward.events import EventType
from docs_steward.process import ProcessResult
from docs_steward.tools import Tool
from docs_steward.yaml_audit import audit_frontmatter

from .fakes import FakeFileSystem, FakeProcessRunner


_BUNDLED = bundled_config_for(Tool.YAMLLINT)
assert _BUNDLED is not None  # tests assume bundled config is reachable
_BASE_ARGV = ("yamllint", "-f", "parsable", "-s", "-c", _BUNDLED, "-")


def _runner_with_yamllint(extra_results: dict | None = None) -> FakeProcessRunner:
    runner = FakeProcessRunner(
        paths={"yamllint": "/usr/bin/yamllint"},
        results=dict(extra_results or {}),
    )
    return runner


class AuditFrontmatterTests(unittest.TestCase):
    def test_missing_yamllint_returns_exit_3(self) -> None:
        events, code = audit_frontmatter(FakeProcessRunner(), FakeFileSystem(), [])
        self.assertEqual(code, 3)
        self.assertEqual(events[0].event, EventType.MISSING)
        self.assertEqual(events[0].tool, Tool.YAMLLINT.value)

    def test_no_files_emits_clean_exit_0(self) -> None:
        runner = _runner_with_yamllint()
        events, code = audit_frontmatter(runner, FakeFileSystem(), [])
        self.assertEqual(code, 0)
        kinds = [e.event for e in events]
        self.assertIn(EventType.SELECTED, kinds)
        self.assertIn(EventType.CLEAN, kinds)

    def test_file_with_clean_frontmatter_yields_no_findings(self) -> None:
        fs = FakeFileSystem(files={"/repo/x.md": "---\nname: foo\n---\nbody\n"})
        runner = _runner_with_yamllint({_BASE_ARGV: ProcessResult(0, "", "")})
        events, code = audit_frontmatter(runner, fs, ["/repo/x.md"])
        self.assertEqual(code, 0)
        # CLEAN event present; no FINDING events.
        self.assertEqual(
            [e for e in events if e.event == EventType.FINDING], []
        )

    def test_finding_routed_with_file_and_anchor(self) -> None:
        fs = FakeFileSystem(files={"/repo/x.md": "---\nname: foo\n---\n"})
        runner = _runner_with_yamllint(
            {
                _BASE_ARGV: ProcessResult(
                    1, "stdin:2:1: [warning] missing document start \"---\" (document-start)\n", ""
                )
            }
        )
        events, code = audit_frontmatter(runner, fs, ["/repo/x.md"])
        self.assertEqual(code, 1)
        findings = [e for e in events if e.event == EventType.FINDING]
        self.assertEqual(len(findings), 1)
        self.assertIn("/repo/x.md:frontmatter", findings[0].detail)  # type: ignore[operator]
        self.assertIn("[warning]", findings[0].detail)  # type: ignore[operator]
        self.assertIn("document-start", findings[0].detail)  # type: ignore[operator]

    def test_stderr_noise_with_clean_stdout_does_not_emit_findings(self) -> None:
        # Regression: _audit_one_block used to concat stdout+stderr
        # before parsing. yamllint can write benign warnings to stderr
        # (deprecation notices, config-resolution traces) on an
        # otherwise clean run; those lines were getting wrapped as
        # fallback FINDING events with the raw stderr text as the
        # detail. yamllint -f parsable puts findings on stdout only —
        # the parse now ignores stderr.
        fs = FakeFileSystem(files={"/repo/x.md": "---\nkey: value\n---\n"})
        runner = _runner_with_yamllint({
            _BASE_ARGV: ProcessResult(
                0,
                "",
                "warning: loading default config (no .yamllint found)\n",
            ),
        })
        events, code = audit_frontmatter(runner, fs, ["/repo/x.md"])
        self.assertEqual(code, 0)
        findings = [e for e in events if e.event == EventType.FINDING]
        self.assertEqual(findings, [])
        kinds = [e.event for e in events]
        self.assertIn(EventType.CLEAN, kinds)

    def test_non_utf8_file_emits_per_file_error_does_not_crash(self) -> None:
        # The schema (events.py + ndjson-schema.md) advertises per-file
        # ERROR coverage for "encoding error". The implementation must
        # catch UnicodeDecodeError (subclass of ValueError, not OSError)
        # alongside OSError or the documented contract breaks: the
        # exception would propagate past audit_frontmatter and crash the
        # CLI instead of becoming a per-file ERROR event.

        class _EncodingErrorFs(FakeFileSystem):
            def read_text(self, path: str) -> str:
                if path == "/repo/badenc.md":
                    raise UnicodeDecodeError("utf-8", b"\xff", 0, 1, "invalid")
                return super().read_text(path)

        fs = _EncodingErrorFs(files={"/repo/clean.md": "---\nkey: value\n---\n"})
        runner = _runner_with_yamllint({_BASE_ARGV: ProcessResult(0, "", "")})
        events, code = audit_frontmatter(
            runner, fs, ["/repo/badenc.md", "/repo/clean.md"],
        )
        # Per-file UnicodeDecodeError -> exit 2 (file error short-circuit).
        self.assertEqual(code, 2)
        errors = [
            e for e in events
            if e.event == EventType.ERROR
            and isinstance(e.detail, dict) and "file" in e.detail
        ]
        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0].detail["file"], "/repo/badenc.md")  # type: ignore[index]
        # Reason string captures the UnicodeDecodeError type so consumers
        # can distinguish encoding errors from OSError variants.
        self.assertIn("UnicodeDecodeError", errors[0].detail["reason"])  # type: ignore[index]

    def test_unreadable_file_with_no_findings_returns_exit_2(self) -> None:
        fs = FakeFileSystem(files={"/repo/ok.md": "---\nkey: value\n---\n"})
        # `/repo/missing.md` is not in fs → read_text raises → recorded as ERROR.
        # /repo/ok.md audits clean, so no FINDING events; the audit must
        # exit 2 (setup/invocation error) rather than 1 (lint findings)
        # because exit 1 would falsely advertise "findings present" to CI.
        runner = _runner_with_yamllint({_BASE_ARGV: ProcessResult(0, "", "")})
        events, code = audit_frontmatter(runner, fs, ["/repo/missing.md", "/repo/ok.md"])
        self.assertEqual(code, 2)
        errors = [e for e in events if e.event == EventType.ERROR]
        self.assertEqual(len(errors), 1)
        self.assertIn("missing.md", errors[0].detail["file"])  # type: ignore[index]

    def test_unreadable_file_plus_real_findings_still_returns_exit_2(self) -> None:
        # Any per-file read error short-circuits to exit 2, regardless of
        # whether real findings also surfaced. The docstring promises
        # exit 2 maps to "a target file was unreadable"; exit 1 would
        # silently drop that signal for a CI consumer who routes the
        # codes differently. Findings ride along in the event stream.
        fs = FakeFileSystem(files={"/repo/dirty.md": "---\nkey: value\n---\n"})
        runner = _runner_with_yamllint({
            _BASE_ARGV: ProcessResult(
                1,
                "stdin:1:1: [warning] missing document start \"---\" (document-start)\n",
                "",
            ),
        })
        events, code = audit_frontmatter(
            runner, fs, ["/repo/missing.md", "/repo/dirty.md"],
        )
        self.assertEqual(code, 2)
        findings = [e for e in events if e.event == EventType.FINDING]
        self.assertEqual(len(findings), 1)
        errors = [
            e for e in events
            if e.event == EventType.ERROR
            and isinstance(e.detail, dict) and "file" in e.detail
        ]
        self.assertEqual(len(errors), 1)

    def test_unreadable_file_error_appears_inline_with_processing_order(self) -> None:
        # Regression: a previous version of the audit loop deferred file
        # errors and appended them after the per-block loop finished, so
        # ERROR events for unreadable files showed up at the bottom of the
        # stream even when those files came first in the input order.
        # Now each ERROR is emitted inline, so the event stream order
        # matches the file-processing order.
        fs = FakeFileSystem(files={
            "/repo/b.md": "---\ndocument-no-newline: value\nkey: value\n---\n",
        })
        runner = _runner_with_yamllint({
            _BASE_ARGV: ProcessResult(
                1, "stdin:1:1: [warning] missing document start \"---\" (document-start)\n", ""
            ),
        })
        events, code = audit_frontmatter(
            runner, fs, ["/repo/missing-first.md", "/repo/b.md"]
        )
        # Per round-6 docstring reconciliation: any file error short-
        # circuits to exit 2 even when findings also surface. The point
        # of this test is the ORDERING of the events, not the exit code.
        self.assertEqual(code, 2)
        # SELECTED + BUNDLED_CONFIG are preamble; after them, file
        # processing should emit the missing-first.md ERROR before the
        # /repo/b.md FINDING, matching the input file order.
        preamble = {EventType.SELECTED, EventType.BUNDLED_CONFIG}
        per_file = [e for e in events if e.event not in preamble]
        self.assertEqual(per_file[0].event, EventType.ERROR)
        self.assertIn(
            "missing-first.md",
            per_file[0].detail["file"],  # type: ignore[index]
        )
        self.assertEqual(per_file[1].event, EventType.FINDING)
        self.assertIn("/repo/b.md", per_file[1].detail)  # type: ignore[operator]

    def test_tool_error_exit_geq_2_emits_error_event_and_exit_2(self) -> None:
        fs = FakeFileSystem(files={"/repo/x.md": "---\nkey: value\n---\n"})
        runner = _runner_with_yamllint(
            {_BASE_ARGV: ProcessResult(2, "", "yamllint config error")}
        )
        events, code = audit_frontmatter(runner, fs, ["/repo/x.md"])
        self.assertEqual(code, 2)
        errors = [e for e in events if e.event == EventType.ERROR]
        self.assertEqual(len(errors), 1)
        # ERROR detail now carries the yamllint stderr text so the
        # consumer sees the actual diagnostic ('yamllint config error')
        # alongside the {exit: 2} signal. Round 9 attached stderr to
        # the invocation-failure path.
        self.assertEqual(
            errors[0].detail, {"exit": 2, "stderr": "yamllint config error"},
        )

    def test_yamllint_strict_warning_exit_2_with_findings_maps_to_exit_1(self) -> None:
        # yamllint -s returns 2 whenever any warning-level finding fires.
        # Earlier the audit treated every exit-2 as an invocation error and
        # emitted ERROR + exit 2 even when yamllint had produced a real
        # parsed warning. Now a non-empty block_events list with rc >= 2
        # is recognized as the strict-warning case and maps to exit 1 +
        # finding events; reserved exit 2 + ERROR for the true-failure
        # case where rc >= 2 BUT block_events is empty.
        fs = FakeFileSystem(files={"/repo/x.md": "---\nkey: value\n---\n"})
        runner = _runner_with_yamllint(
            {
                _BASE_ARGV: ProcessResult(
                    2,
                    "stdin:2:3: [warning] wrong indentation: expected 2 but found 4 (indentation)\n",
                    "",
                ),
            }
        )
        events, code = audit_frontmatter(runner, fs, ["/repo/x.md"])
        self.assertEqual(code, 1)
        findings = [e for e in events if e.event == EventType.FINDING]
        self.assertEqual(len(findings), 1)
        self.assertIn("indentation", findings[0].detail)  # type: ignore[operator]
        # No ERROR event — the warning was a finding, not an invocation failure.
        invocation_errors = [
            e for e in events
            if e.event == EventType.ERROR and isinstance(e.detail, dict) and "exit" in e.detail
        ]
        self.assertEqual(invocation_errors, [])

    def test_explicit_config_path_overrides_bundled(self) -> None:
        fs = FakeFileSystem(files={"/repo/x.md": "---\nkey: value\n---\n"})
        custom_argv = (
            "yamllint", "-f", "parsable", "-s", "-c", "/custom/.yamllint", "-"
        )
        runner = _runner_with_yamllint({custom_argv: ProcessResult(0, "", "")})
        events, code = audit_frontmatter(
            runner, fs, ["/repo/x.md"], config_path="/custom/.yamllint"
        )
        self.assertEqual(code, 0)
        selected = [e for e in events if e.event == EventType.SELECTED][0]
        self.assertEqual(selected.detail["config_source"], "repo")  # type: ignore[index]
        self.assertEqual(selected.detail["config_path"], "/custom/.yamllint")  # type: ignore[index]
        # No bundled-config event when override is in effect.
        self.assertEqual(
            [e for e in events if e.event == EventType.BUNDLED_CONFIG], []
        )

    def test_fenced_yaml_blocks_are_scanned(self) -> None:
        body = (
            "---\nkey1: 1\n---\n\n"
            "# heading\n\n"
            "```yaml\nkey2: 2\n```\n"
        )
        fs = FakeFileSystem(files={"/repo/x.md": body})
        runner = _runner_with_yamllint({_BASE_ARGV: ProcessResult(0, "", "")})
        events, code = audit_frontmatter(runner, fs, ["/repo/x.md"])
        self.assertEqual(code, 0)
        # Verify yamllint was invoked twice (once per block).
        invocations = [c for c in runner.calls if c[0] == _BASE_ARGV]
        self.assertEqual(len(invocations), 2)
        # Stdin payloads should reflect the two block contents.
        stdins = [c[2] for c in invocations]
        self.assertIn("key1: 1", stdins[0])
        self.assertIn("key2: 2", stdins[1])


if __name__ == "__main__":
    unittest.main()
