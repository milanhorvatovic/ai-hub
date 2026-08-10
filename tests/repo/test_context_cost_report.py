"""Unit tests for the context-cost reporter (`.github/scripts/report_context_cost.py`).

Stdlib-only and loaded from its file path, in the same spirit as the commit-style
and PR-title validator tests: the script lives outside the importable package
tree because CI runs it directly.
"""

import importlib.util
import json
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SCRIPT = _REPO_ROOT / ".github" / "scripts" / "report_context_cost.py"
_WORKFLOW = _REPO_ROOT / ".github" / "workflows" / "tests.yml"


def _load_module():
    spec = importlib.util.spec_from_file_location("report_context_cost", _SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


reporter = _load_module()

COST = {"discovery_bytes": 100, "skill_md_bytes": 200, "load_bytes": 300, "files": 4}


def test_an_unchanged_fleet_reports_that_and_no_table() -> None:
    """A PR touching no skill should say so rather than print a table of zeros."""
    out = reporter.render({"alpha": COST}, {"alpha": COST})

    assert reporter.NO_CHANGE in out
    assert "|" not in out


def test_only_the_skills_that_moved_appear() -> None:
    grew = COST | {"skill_md_bytes": 200 + 512}
    out = reporter.render({"alpha": COST, "beta": COST}, {"alpha": grew, "beta": COST})

    assert "alpha" in out
    assert "beta" not in out
    assert "200 → 712 (+512)" in out


def test_a_shrinking_load_tree_reads_as_a_loss_not_a_gain() -> None:
    """Signed deltas, so the direction survives a skim."""
    out = reporter.render({"alpha": COST}, {"alpha": COST | {"load_bytes": 300 - 34}})

    assert "300 → 266 (-34)" in out


def test_a_missing_base_baseline_reports_every_skill_as_new(tmp_path: Path) -> None:
    """The PR that introduces the baseline has no base copy, which is reportable.

    The workflow lets `git show` fail into an empty file rather than failing the
    step, so this is the shape the reporter actually receives that one time.
    """
    base = tmp_path / "absent.json"
    head = tmp_path / "head.json"
    head.write_text(json.dumps({"alpha": COST}), encoding="utf-8")

    out = reporter.render(reporter._load(base), reporter._load(head))

    assert "(new)" in out
    assert "alpha" in out


def test_a_deleted_skill_is_not_silently_dropped() -> None:
    out = reporter.render({"alpha": COST}, {})

    assert "alpha" in out
    assert "(gone)" in out


def test_the_report_runs_where_history_is_available() -> None:
    """Its own job with a full checkout, not a step on a shallow matrix leg.

    A merge base cannot be computed from a depth-one clone, and deepening the
    four pytest legs to serve a report nobody gates on is the wrong trade.
    """
    workflow = _WORKFLOW.read_text(encoding="utf-8")

    assert "report_context_cost.py" in workflow
    assert "context-cost:" in workflow
    assert "fetch-depth: 0" in workflow


def test_the_comparison_point_is_the_merge_base() -> None:
    """Not `base.sha`, which is the base branch tip at event time.

    That tip moves as other pull requests merge, so comparing against it
    attributes their changes — in reverse — to this one, and disagrees with the
    three-dot diff the reviewer is reading. On a pull_request checkout the merge
    commit's parents give the real merge base.
    """
    workflow = _WORKFLOW.read_text(encoding="utf-8")

    assert "git merge-base HEAD^1 HEAD^2" in workflow
    # The interpolation, not the words: the comment beside it names `base.sha`
    # to say why it is the wrong commit, and forbidding the substring would make
    # the explanation and the check unable to coexist.
    assert "${{ github.event.pull_request.base.sha }}" not in workflow
