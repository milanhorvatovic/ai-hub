"""SubprocessRunner — PATH augmentation behavior (no actual subprocess calls).

The body of `run()` and `which()` against real binaries is covered by smoke
tests; here we exercise the pure logic of _augment_path and the constructor's
env-augmentation behavior.
"""

from __future__ import annotations

import os
import os.path
import sys
import tempfile
import unittest

from docs_steward.process import SubprocessRunner, _augment_path


class AugmentPathTests(unittest.TestCase):
    def test_empty_base_appends_existing_dirs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = _augment_path("", (tmp,))
            self.assertEqual(result, tmp)

    def test_missing_extras_skipped(self) -> None:
        result = _augment_path("/usr/bin", ("/does/not/exist/anywhere",))
        self.assertEqual(result, "/usr/bin")

    def test_duplicate_extras_deduplicated(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = f"/usr/bin{os.pathsep}{tmp}"
            result = _augment_path(base, (tmp,))
            self.assertEqual(result.count(tmp), 1)

    def test_existing_path_preserved_in_order(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = f"/usr/local/bin{os.pathsep}/usr/bin"
            result = _augment_path(base, (tmp,))
            parts = result.split(os.pathsep)
            self.assertEqual(parts[0], "/usr/local/bin")
            self.assertEqual(parts[1], "/usr/bin")
            self.assertEqual(parts[-1], tmp)

    def test_user_home_expansion(self) -> None:
        # ~ should expand; if the expanded dir exists it's added, otherwise skipped.
        home_bin = os.path.expanduser("~")
        if os.path.isdir(home_bin):
            result = _augment_path("/usr/bin", ("~",))
            self.assertIn(home_bin, result.split(os.pathsep))


class SubprocessRunnerRunErrorHandlingTests(unittest.TestCase):
    """`run()` must convert OS-level exec failures into ProcessResult objects;
    propagating them would force every caller to wrap run() in try/except and
    crash the CLI on hiccups the orchestration layer can already handle."""

    def test_missing_binary_returns_127(self) -> None:
        runner = SubprocessRunner(extra_path_dirs=())
        result = runner.run(["/nonexistent/path/to/binary"])
        self.assertEqual(result.returncode, 127)
        self.assertEqual(result.stdout, "")
        # Stderr carries the FileNotFoundError string; exact wording is
        # OS-dependent (POSIX shows the path; Windows shows
        # "[WinError 2] The system cannot find the file specified"
        # without the path). Just assert something was captured.
        self.assertTrue(result.stderr)

    @unittest.skipIf(
        sys.platform == "win32",
        "POSIX-only: chmod -x doesn't render a file unexecutable on Windows.",
    )
    def test_non_executable_binary_returns_126(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "no-exec")
            with open(path, "w", encoding="utf-8") as fh:
                fh.write("#!/bin/sh\necho ok\n")
            os.chmod(path, 0o644)  # readable, NOT executable
            runner = SubprocessRunner(extra_path_dirs=())
            result = runner.run([path])
            self.assertEqual(result.returncode, 126)
            self.assertEqual(result.stdout, "")
            # PermissionError vs IsADirectoryError both arrive here; tolerant.
            self.assertTrue(result.stderr)

    @unittest.skipIf(
        sys.platform == "win32",
        "POSIX-only: passing a directory as an executable raises OSError on POSIX.",
    )
    def test_directory_as_binary_returns_126(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            runner = SubprocessRunner(extra_path_dirs=())
            result = runner.run([tmp])
            self.assertEqual(result.returncode, 126)
            self.assertEqual(result.stdout, "")
            self.assertTrue(result.stderr)


class SubprocessRunnerUtf8DecodeTests(unittest.TestCase):
    """`run()` must decode child stdout/stderr as UTF-8 regardless of the
    platform default — Windows CI is cp1252, and prettier / yamllint
    routinely emit smart quotes, ellipses, and em-dashes that would
    otherwise raise UnicodeDecodeError on Windows."""

    def test_runs_command_emitting_utf8_smart_quotes(self) -> None:
        # POSIX `printf` emits the UTF-8 bytes for `…` (E2 80 A6) and
        # `“`/`”`. With `text=True` + platform-default encoding this
        # would crash on cp1252; with `encoding="utf-8"` it round-trips.
        runner = SubprocessRunner(extra_path_dirs=())
        result = runner.run(
            ["printf", "%s", "smart “quotes” and ellipsis …"]
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn("“quotes”", result.stdout)
        self.assertIn("…", result.stdout)

    def test_non_utf8_byte_replaced_rather_than_raised(self) -> None:
        # A bare 0xff is not valid UTF-8; `errors="replace"` swaps in
        # U+FFFD instead of raising UnicodeDecodeError. Use python -c
        # so the byte reaches subprocess stdout untranslated regardless
        # of shell quoting / printf %b behaviour.
        import sys as _sys
        runner = SubprocessRunner(extra_path_dirs=())
        result = runner.run(
            [_sys.executable, "-c", "import sys; sys.stdout.buffer.write(b'\\xff')"],
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn("�", result.stdout)


class SubprocessRunnerConstructorTests(unittest.TestCase):
    def test_augments_path_with_existing_extras(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            runner = SubprocessRunner(extra_path_dirs=(tmp,))
            self.assertIn(tmp, runner._env["PATH"])  # noqa: SLF001 — internal check
            # Original PATH must be preserved.
            for original_dir in os.environ.get("PATH", "").split(os.pathsep):
                if original_dir:
                    self.assertIn(original_dir, runner._env["PATH"])  # noqa: SLF001

    def test_empty_extras_leaves_path_unchanged(self) -> None:
        runner = SubprocessRunner(extra_path_dirs=())
        self.assertEqual(runner._env["PATH"], os.environ.get("PATH", ""))  # noqa: SLF001

    @unittest.skipIf(
        sys.platform == "win32",
        "shutil.which on Windows requires a PATHEXT extension (.exe/.bat/.cmd); "
        "shebang-based fake binaries are POSIX-only",
    )
    def test_which_uses_augmented_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            # Create a fake executable in the extra dir.
            fake = os.path.join(tmp, "fake-tool-for-test")
            with open(fake, "w", encoding="utf-8") as fh:
                fh.write("#!/bin/sh\necho ok\n")
            os.chmod(fake, 0o755)

            runner = SubprocessRunner(extra_path_dirs=(tmp,))
            resolved = runner.which("fake-tool-for-test")
            self.assertEqual(resolved, fake)


if __name__ == "__main__":
    unittest.main()
