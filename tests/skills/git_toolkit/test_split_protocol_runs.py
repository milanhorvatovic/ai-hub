"""Execute SPLIT's documented apply protocol instead of describing it.

Every other contract test in this package grades shipped text, which is the
right instrument for a rule and the wrong one for a recipe. The recipe was wrong
twice in ways no prose check could see: `git add` against an already-staged
index is a no-op, so the first commit took the whole pile, and `git rev-parse
HEAD` aborts the run on a repository that has no commits yet. Both were found by
running the commands, so running them is what guards them.

The commands are read out of `capability.md` rather than restated here. A copy
would drift into passing while the shipped recipe rotted, which is the failure
this file exists to make impossible.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[3]
_CAPABILITY = _REPO_ROOT / "skills/git-toolkit/capabilities/commit-message/capability.md"

# The fence splits into a prologue that runs once and a body that runs per
# partition. The marker is the comment the recipe already carries, so the split
# is the document's own structure rather than an offset this file invents.
# The marker is a whole line on purpose: splitting mid-comment leaves prose at
# the head of the loop body, which is a syntax error rather than a failed test.
_PER_PARTITION_MARKER = "# per partition, in series order:\n"

_ENV = {
    "GIT_CONFIG_GLOBAL": "/dev/null",
    "GIT_CONFIG_SYSTEM": "/dev/null",
    "GIT_AUTHOR_NAME": "T",
    "GIT_AUTHOR_EMAIL": "t@example.invalid",
    "GIT_COMMITTER_NAME": "T",
    "GIT_COMMITTER_EMAIL": "t@example.invalid",
    "PATH": "/usr/bin:/bin:/usr/local/bin",
}


def _usable_bash() -> str | None:
    """A bash that parses, not merely a name on PATH.

    Windows runners resolve `bash` to the WSL launcher stub, which exists, runs,
    and exits non-zero without parsing anything — the same trap the code-sample
    lane documents.
    """
    exe = shutil.which("bash")
    if not exe:
        return None
    probe = subprocess.run([exe, "-n"], input="true\n", text=True, capture_output=True)
    return exe if probe.returncode == 0 else None


_BASH = _usable_bash()
needs_bash = pytest.mark.skipif(
    _BASH is None, reason="no bash that can run the shipped recipe"
)


@pytest.fixture(scope="session")
def protocol() -> tuple[str, str]:
    """(prologue, per-partition body) read from the shipped bash fence."""
    text = _CAPABILITY.read_text(encoding="utf-8")
    fence = re.search(r"```bash\n(.*?)```", text, re.DOTALL)
    assert fence, "capability.md no longer ships the apply protocol as a bash fence"
    body = fence.group(1)
    assert _PER_PARTITION_MARKER in body, (
        "the recipe lost its per-partition marker, so this test can no longer "
        "tell the one-time setup from the loop body"
    )
    prologue, _, per_partition = body.partition(_PER_PARTITION_MARKER)
    return prologue, per_partition


def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args], cwd=repo, capture_output=True, text=True, env=_ENV, check=True
    )
    return result.stdout


def _run_series(
    repo: Path, protocol: tuple[str, str], partitions: list[list[str]]
) -> subprocess.CompletedProcess[str]:
    """Run the shipped prologue once, then its body once per partition.

    `SNAPSHOT` and `ORIGINAL` are set by the prologue and read by the body, so
    the whole series runs in one shell — splitting it into separate processes
    would quietly test different code than the recipe describes.

    Two things this harness must not do, both found by review. It must not add
    shell flags: the recipe carries its own `set -euo pipefail`, and supplying
    them here would test fail-fast semantics the shipped text does not have.
    And it must not paste filenames into shell source — a legal staged name may
    contain a quote or `$(…)`, which would execute during an apply. Paths reach
    the script the way the recipe says they do, NUL-separated through a file
    whose own name this test chooses.
    """
    prologue, per_partition = protocol
    control = repo / ".protocol-control"
    control.mkdir(exist_ok=True)
    script = [prologue]
    for index, paths in enumerate(partitions):
        (control / f"msg{index}").write_text(f"commit {index}\n", encoding="utf-8")
        (control / f"part{index}").write_bytes(
            b"".join(p.encode() + b"\0" for p in paths)
        )
        script.append(f'PARTITION_FILE="{control}/part{index}"')
        script.append(f'MESSAGE_FILE="{control}/msg{index}"')
        script.append(per_partition)
    runner = repo / ".protocol-control" / "run.bash"
    runner.write_text("\n".join(script), encoding="utf-8")
    result = subprocess.run(
        [_BASH, str(runner)], cwd=repo, capture_output=True, text=True, env=_ENV
    )
    return result


def _run_ok(repo: Path, protocol, partitions: list[list[str]]) -> None:
    result = _run_series(repo, protocol, partitions)
    assert result.returncode == 0, (
        f"the shipped protocol failed:\nstdout={result.stdout}\nstderr={result.stderr}"
    )


def _init(repo: Path) -> None:
    subprocess.run(["git", "init", "-q", "-b", "main", str(repo)], check=True, env=_ENV)


@needs_bash
def test_each_partition_commits_only_its_own_paths(tmp_path: Path, protocol) -> None:
    """The defect that shipped: `git add` on a staged index isolates nothing.

    With the whole pile staged, the first commit took every partition and the
    rest were empty. Asserting per-commit contents is the only way to see it —
    the recipe reads plausibly either way.
    """
    repo = tmp_path / "history"
    repo.mkdir()
    _init(repo)
    for name in ("a.txt", "b.txt", "c.txt"):
        (repo / name).write_text("base\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "base")

    (repo / "a.txt").write_text("base\nP1\n", encoding="utf-8")
    (repo / "b.txt").write_text("base\nP2\n", encoding="utf-8")
    (repo / "c.txt").write_text("base\nSTAGED\n", encoding="utf-8")
    _git(repo, "add", "-A")
    # c.txt now carries a hunk the user deliberately did not stage.
    (repo / "c.txt").write_text("base\nSTAGED\nWITHHELD\n", encoding="utf-8")

    _run_ok(repo, protocol, [["a.txt"], ["b.txt", "c.txt"]])

    first = _git(repo, "show", "--name-only", "--format=", "HEAD~1").split()
    second = _git(repo, "show", "--name-only", "--format=", "HEAD").split()
    assert first == ["a.txt"], f"partition 1 committed {first}, not its own paths alone"
    assert sorted(second) == ["b.txt", "c.txt"], f"partition 2 committed {second}"

    committed = _git(repo, "show", "HEAD:c.txt")
    assert "WITHHELD" not in committed, (
        "the protocol staged c.txt from the working tree, committing a hunk the "
        "user left unstaged — curation reversed rather than honoured"
    )
    assert " M c.txt" in _git(repo, "status", "--porcelain"), (
        "the withheld hunk did not survive as an unstaged change"
    )


@needs_bash
def test_the_protocol_creates_a_first_commit(tmp_path: Path, protocol) -> None:
    """An unborn branch has no HEAD, and this path is now the common one.

    Routing every staged authoring request through SPLIT put a repository's first
    commit on this recipe. An unguarded `git rev-parse HEAD` aborts before any
    partition is written, which a text check cannot distinguish from a recipe
    that works.
    """
    repo = tmp_path / "unborn"
    repo.mkdir()
    _init(repo)
    (repo / "a.txt").write_text("x\n", encoding="utf-8")
    (repo / "b.txt").write_text("y\n", encoding="utf-8")
    _git(repo, "add", "-A")

    _run_ok(repo, protocol, [["a.txt"], ["b.txt"]])

    assert _git(repo, "rev-list", "--count", "HEAD").strip() == "2", (
        "the series did not produce two commits on a branch that had none"
    )
    assert _git(repo, "show", "--name-only", "--format=", "HEAD~1").split() == ["a.txt"]
    assert _git(repo, "show", "--name-only", "--format=", "HEAD").split() == ["b.txt"]


@pytest.fixture(scope="session")
def reversals() -> tuple[str, str]:
    """(parented, unborn) undo commands, read from the shipped output block.

    The previous version of this test restated `reset` and `update-ref` from
    memory, so the output block a user copies could regress while the semantics
    it claims to check stayed green — the same gap the apply protocol had before
    it was executed rather than described.
    """
    text = _CAPABILITY.read_text(encoding="utf-8")
    marker = "Undo the whole series with:"
    assert marker in text, "the output block no longer advertises a reversal"
    lines = text.split(marker, 1)[1].splitlines()
    plain = next(ln.strip() for ln in lines if ln.strip().startswith("git "))
    commented = next(
        ln.split(":", 1)[1].strip() for ln in lines if ln.strip().startswith("# ")
    )
    return plain, commented


@needs_bash
def test_the_documented_reversals_resolve(tmp_path: Path, protocol, reversals) -> None:
    """Both advertised undo commands, against the trees each names.

    `HEAD~N` is the reversal for a series with a parent and cannot resolve for
    one that began unborn, where N commits leave no N-th ancestor. Both are run
    exactly as the output block spells them, with only the count substituted.
    """
    parented_cmd, unborn_cmd = reversals

    with_parent = tmp_path / "parent"
    with_parent.mkdir()
    _init(with_parent)
    (with_parent / "seed.txt").write_text("seed\n", encoding="utf-8")
    _git(with_parent, "add", "-A")
    _git(with_parent, "commit", "-qm", "seed")
    base = _git(with_parent, "rev-parse", "HEAD").strip()
    (with_parent / "a.txt").write_text("a\n", encoding="utf-8")
    (with_parent / "b.txt").write_text("b\n", encoding="utf-8")
    _git(with_parent, "add", "-A")
    _run_ok(with_parent, protocol, [["a.txt"], ["b.txt"]])
    _git(with_parent, *parented_cmd.split()[1:])
    assert _git(with_parent, "rev-parse", "HEAD").strip() == base, (
        f"the advertised reversal {parented_cmd!r} did not return the series to its base"
    )

    unborn = tmp_path / "unborn-undo"
    unborn.mkdir()
    _init(unborn)
    (unborn / "a.txt").write_text("a\n", encoding="utf-8")
    _git(unborn, "add", "-A")
    _run_ok(unborn, protocol, [["a.txt"]])
    failed = subprocess.run(
        ["git", *parented_cmd.replace("2", "1").split()[1:]],
        cwd=unborn, capture_output=True, text=True, env=_ENV,
    )
    assert failed.returncode != 0, (
        "the parented reversal resolved on a series that began unborn, so the "
        "block's second command would be unnecessary — recheck which applies"
    )
    _git(unborn, *unborn_cmd.split()[1:])
    assert "A  a.txt" in _git(unborn, "status", "--porcelain"), (
        f"the advertised unborn reversal {unborn_cmd!r} did not return the branch "
        "to unborn with the tree staged"
    )


@needs_bash
def test_a_partition_path_is_never_a_pattern(tmp_path: Path, protocol) -> None:
    """A filename is not a pathspec, and git disagrees unless told.

    `a[1].txt` is a legal name whose characters are also a character class, so a
    bare pathspec stages its neighbour `a1.txt` too — measured, not theorised.
    On a verb that applies by default the result is a commit containing another
    partition's file, which no message describes.
    """
    repo = tmp_path / "globby"
    repo.mkdir()
    _init(repo)
    for name in ("a[1].txt", "a1.txt"):
        (repo / name).write_text("base\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "base")
    for name in ("a[1].txt", "a1.txt"):
        (repo / name).write_text("changed\n", encoding="utf-8")
    _git(repo, "add", "-A")

    _run_ok(repo, protocol, [["a[1].txt"], ["a1.txt"]])

    first = _git(repo, "show", "--name-only", "--format=", "HEAD~1").split("\n")
    assert [f for f in first if f] == ["a[1].txt"], (
        f"the bracketed name matched as a pattern and pulled in a sibling: {first}"
    )


@needs_bash
def test_a_rename_keeps_both_of_its_paths(tmp_path: Path, protocol) -> None:
    """Restoring only the destination records an add and orphans the deletion.

    The source entry stands from HEAD, so the commit says a file appeared rather
    than moved and the removal lands in whichever partition follows — or in none.
    """
    repo = tmp_path / "renamed"
    repo.mkdir()
    _init(repo)
    (repo / "old.txt").write_text("content\n", encoding="utf-8")
    (repo / "z.txt").write_text("other\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "base")
    _git(repo, "mv", "old.txt", "new.txt")
    _git(repo, "add", "-A")

    _run_ok(repo, protocol, [["old.txt", "new.txt"]])

    status = _git(repo, "show", "--name-status", "--format=", "HEAD", "-M")
    assert status.startswith("R"), (
        f"the commit records {status.split()[0]!r} rather than a rename, so the "
        "source deletion was left behind"
    )
    assert "old.txt" not in _git(repo, "status", "--porcelain"), (
        "the rename's source is still pending after its partition committed"
    )


@needs_bash
def test_a_filename_cannot_execute_during_an_apply(tmp_path: Path, protocol) -> None:
    """Staged names are data; a recipe that pastes them into itself makes them code.

    `$(…)`, a backtick, and a quote are all legal in a POSIX filename, and the
    verb applies by default — so a path reaching the script as text is command
    execution on someone else's repository. The canary is a file the payload
    would create; the assertion is that it never appears.
    """
    repo = tmp_path / "hostile"
    repo.mkdir()
    _init(repo)
    canary = repo / "PWNED"
    hostile = '$(touch PWNED)"; touch PWNED; #.txt'
    (repo / hostile).write_text("payload\n", encoding="utf-8")
    (repo / "innocent.txt").write_text("fine\n", encoding="utf-8")
    _git(repo, "add", "-A")

    _run_ok(repo, protocol, [[hostile], ["innocent.txt"]])

    assert not canary.exists(), (
        "a staged filename executed during the apply — the recipe or its caller "
        "is interpolating paths into shell source"
    )
    # `-z` because git quotes special characters in its default path output, so
    # a plain comparison fails on a name this test exists to exercise.
    raw = _git(repo, "show", "--name-only", "--format=", "-z", "HEAD~1")
    first = [f for f in raw.split("\0") if f]
    assert first == [hostile], f"the hostile name did not commit as itself: {first}"


@needs_bash
def test_a_rejected_commit_stops_the_series(tmp_path: Path, protocol) -> None:
    """Strict mode has to live in the recipe, not in whoever invokes it.

    A pre-commit hook rejecting one partition returns non-zero; without `set -e`
    the loop continues and builds a partial series in the wrong order, with an
    undo count that no longer matches what exists.
    """
    repo = tmp_path / "hooked"
    repo.mkdir()
    _init(repo)
    (repo / "a.txt").write_text("a\n", encoding="utf-8")
    (repo / "b.txt").write_text("b\n", encoding="utf-8")
    _git(repo, "add", "-A")
    # Rejects only the first partition. A hook that rejects everything cannot
    # distinguish fail-fast from a second failure: both leave a non-zero exit and
    # no commits, so the test passed with `set -e` deleted. Mutation found that.
    # `commit-msg`, not `pre-commit`: only the former is handed the message file,
    # which is how this rejects one partition rather than all of them.
    hook = repo / ".git" / "hooks" / "commit-msg"
    hook.write_text('#!/bin/sh\ngrep -q "commit 0" "$1" && exit 1\nexit 0\n', encoding="utf-8")
    hook.chmod(0o755)

    result = _run_series(repo, protocol, [["a.txt"], ["b.txt"]])

    assert result.returncode != 0, (
        "the series ran to completion despite a rejected commit, so the recipe "
        "does not fail fast on its own"
    )
    assert _git(repo, "rev-list", "--count", "--all").strip() == "0", (
        "the second partition committed after the first was rejected — the loop "
        "continued past a failure, which is what strict mode exists to prevent"
    )
