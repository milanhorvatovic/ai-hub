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

    def test_unreadable_file_emits_error_but_continues(self) -> None:
        fs = FakeFileSystem(files={"/repo/ok.md": "---\nkey: value\n---\n"})
        # `/repo/missing.md` is not in fs → read_text raises → recorded as ERROR.
        runner = _runner_with_yamllint({_BASE_ARGV: ProcessResult(0, "", "")})
        events, code = audit_frontmatter(runner, fs, ["/repo/missing.md", "/repo/ok.md"])
        # Exit 1 because of the unreadable file; CLEAN suppressed.
        self.assertEqual(code, 1)
        errors = [e for e in events if e.event == EventType.ERROR]
        self.assertEqual(len(errors), 1)
        self.assertIn("missing.md", errors[0].detail["file"])  # type: ignore[index]

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
        self.assertEqual(code, 1)
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
        self.assertEqual(errors[0].detail, {"exit": 2})

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
