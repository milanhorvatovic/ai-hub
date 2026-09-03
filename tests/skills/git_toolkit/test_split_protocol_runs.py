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
_PER_PARTITION_MARKER = "# per partition, in series order:"

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


def _run_series(repo: Path, protocol: tuple[str, str], partitions: list[list[str]]) -> None:
    """Run the shipped prologue once, then its body once per partition.

    `SNAPSHOT` and `ORIGINAL` are set by the prologue and read by the body, so
    the whole series runs in one shell — splitting it into separate processes
    would quietly test different code than the recipe describes.
    """
    prologue, per_partition = protocol
    script = [prologue]
    for index, paths in enumerate(partitions):
        message = repo / f"msg{index}"
        message.write_text(f"commit {index}\n", encoding="utf-8")
        quoted = " ".join(f'"{p}"' for p in paths)
        script.append(f"PARTITION_PATHS=({quoted})")
        script.append(f'MESSAGE_FILE="{message}"')
        script.append(per_partition)
    result = subprocess.run(
        [_BASH, "-e", "-u", "-o", "pipefail", "-c", "\n".join(script)],
        cwd=repo, capture_output=True, text=True, env=_ENV,
    )
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

    _run_series(repo, protocol, [["a.txt"], ["b.txt", "c.txt"]])

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

    _run_series(repo, protocol, [["a.txt"], ["b.txt"]])

    assert _git(repo, "rev-list", "--count", "HEAD").strip() == "2", (
        "the series did not produce two commits on a branch that had none"
    )
    assert _git(repo, "show", "--name-only", "--format=", "HEAD~1").split() == ["a.txt"]
    assert _git(repo, "show", "--name-only", "--format=", "HEAD").split() == ["b.txt"]


@needs_bash
def test_the_documented_reversals_resolve(tmp_path: Path, protocol) -> None:
    """Both undo commands, against the trees they are advertised for.

    `HEAD~N` is the reversal for a series with a parent and does not resolve for
    one that began unborn — where N commits leave no N-th ancestor. The output
    block offers both; this runs both against the case each names.
    """
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
    _run_series(with_parent, protocol, [["a.txt"], ["b.txt"]])
    _git(with_parent, "reset", "--soft", "HEAD~2")
    assert _git(with_parent, "rev-parse", "HEAD").strip() == base, (
        "`git reset --soft HEAD~N` did not return a parented series to its base"
    )

    unborn = tmp_path / "unborn-undo"
    unborn.mkdir()
    _init(unborn)
    (unborn / "a.txt").write_text("a\n", encoding="utf-8")
    _git(unborn, "add", "-A")
    _run_series(unborn, protocol, [["a.txt"]])
    result = subprocess.run(
        ["git", "reset", "--soft", "HEAD~1"],
        cwd=unborn, capture_output=True, text=True, env=_ENV,
    )
    assert result.returncode != 0, (
        "HEAD~N resolved on a series that began unborn, so the output block's "
        "second reversal would be unnecessary — recheck which command applies"
    )
    _git(unborn, "update-ref", "-d", "HEAD")
    assert "A  a.txt" in _git(unborn, "status", "--porcelain"), (
        "deleting the ref did not return the branch to unborn with the tree staged"
    )
