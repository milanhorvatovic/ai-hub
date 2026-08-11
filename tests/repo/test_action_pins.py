"""Unit and tree-level tests for the action-pin checker (`.github/scripts/check_action_pins.py`).

The checker scans workflow and composite-action text line by line because the
trailing-comment rule lives in comments, which a YAML parser drops. That leaves
one hole — a `uses:` written in a shape the line regex does not match, such as
a flow mapping — so the checker's own `--verify-completeness` mode parses every
file with PyYAML and fails on any disagreement, bound to source lines so equal
values cannot cancel. The gate runs that mode from the base branch; the tests
here hold the same comparison against the tree and pin the gate's wiring.
"""

import importlib.util
import sys
from pathlib import Path

import pytest
import yaml

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SCRIPT = _REPO_ROOT / ".github" / "scripts" / "check_action_pins.py"
_WORKFLOW_DIR = _REPO_ROOT / ".github" / "workflows"

_SHA = "de0fac2e4500dabe0009e67214ff5f5447ce83dd"


def _load_module():
    spec = importlib.util.spec_from_file_location("check_action_pins", _SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    # Registered before exec so the dataclass machinery can resolve the
    # module's postponed annotations through sys.modules.
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


checker = _load_module()


def _write_workflow(root: Path, body: str, name: str = "sample.yml") -> Path:
    workflows = root / ".github" / "workflows"
    workflows.mkdir(parents=True, exist_ok=True)
    target = workflows / name
    target.write_text(body, encoding="utf-8")
    return target


def _scan_snippet(root: Path, body: str) -> list:
    _write_workflow(root, body)
    return checker.scan(root)


@pytest.mark.parametrize(
    "step",
    [
        f"      - uses: actions/checkout@{_SHA} # v6.0.2\n",
        f'      - uses: "actions/checkout@{_SHA}" # v6.0.2\n',
        f"      - uses: github/codeql-action/init@{_SHA} # v4.37.4\n",
        f"      - uses: actions/checkout@{_SHA} # 6.0.2\n",
        f"      - uses: owner/repo/.github/workflows/reusable.yml@{_SHA} # v1.2.3\n",
        "      - uses: docker://alpine@sha256:c5b1261d6d3e43071626931fc004f70149baeba2c8ec672bd4f27761f8e1ad6b\n",
    ],
    ids=[
        "sha-with-trailing-version",
        "quoted-value",
        "action-subpath",
        "bare-version-token",
        "reusable-workflow-sha",
        "docker-digest",
    ],
)
def test_compliant_reference_passes(tmp_path: Path, step: str) -> None:
    findings = _scan_snippet(tmp_path, f"jobs:\n  a:\n    steps:\n{step}")
    assert findings == []


@pytest.mark.parametrize(
    ("step", "problem_fragment"),
    [
        ("      - uses: actions/checkout@v4\n", "not a full 40-hex commit SHA"),
        ("      - uses: actions/checkout@main\n", "not a full 40-hex commit SHA"),
        (f"      - uses: actions/checkout@{_SHA[:12]}\n", "not a full 40-hex commit SHA"),
        ("      - uses: actions/checkout\n", "no ref at all"),
        (f"      - uses: actions/checkout@{_SHA}\n", "no trailing version comment"),
        (f"      - uses: actions/checkout@{_SHA} # pinned for stability\n", "not a bare version token"),
        (f"      - uses: actions/checkout@{_SHA} # v6.0.2 and some prose\n", "not a bare version token"),
        ("      - uses: docker://alpine:3.19\n", "pinned by a full digest"),
        ("      - uses: docker://alpine@sha256:c5b1261d6d3e\n", "pinned by a full digest"),
        (
            f"      # actions/checkout v4.3.0\n      - uses: actions/checkout@{_SHA} # v6.0.2\n",
            "line above the pin",
        ),
    ],
    ids=[
        "tag-ref",
        "branch-ref",
        "short-sha",
        "no-ref",
        "missing-comment",
        "prose-comment",
        "version-plus-prose",
        "docker-tag",
        "docker-short-digest",
        "version-comment-above",
    ],
)
def test_violating_reference_fails(tmp_path: Path, step: str, problem_fragment: str) -> None:
    findings = _scan_snippet(tmp_path, f"jobs:\n  a:\n    steps:\n{step}")
    assert len(findings) == 1
    assert problem_fragment in findings[0].problem


def test_prose_comment_above_without_version_is_fine(tmp_path: Path) -> None:
    body = (
        "jobs:\n  a:\n    steps:\n"
        "      # Check out the BASE branch so the PR cannot edit its own judge.\n"
        f"      - uses: actions/checkout@{_SHA} # v6.0.2\n"
    )
    assert _scan_snippet(tmp_path, body) == []


def test_finding_reports_file_and_line(tmp_path: Path) -> None:
    body = "jobs:\n  a:\n    steps:\n      - uses: actions/checkout@v4\n"
    (finding,) = _scan_snippet(tmp_path, body)
    assert finding.path.name == "sample.yml"
    assert finding.line == 4


def test_composite_action_manifest_is_scanned(tmp_path: Path) -> None:
    # The local `./` exemption is sound only because its target is scanned too;
    # a manifest smuggling a mutable remote reference must fail on its own.
    manifest = tmp_path / ".github" / "actions" / "local-thing" / "action.yml"
    manifest.parent.mkdir(parents=True)
    manifest.write_text(
        "runs:\n  using: composite\n  steps:\n    - uses: owner/action@main\n",
        encoding="utf-8",
    )
    (finding,) = checker.scan(tmp_path)
    assert finding.path == manifest
    assert "not a full 40-hex commit SHA" in finding.problem


def test_local_action_anywhere_in_the_tree_is_scanned(tmp_path: Path) -> None:
    # Local actions are not confined to .github/actions — the scan set follows
    # each `./` reference to wherever its manifest lives.
    _write_workflow(tmp_path, "jobs:\n  a:\n    steps:\n      - uses: ./ci/local\n")
    manifest = tmp_path / "ci" / "local" / "action.yml"
    manifest.parent.mkdir(parents=True)
    manifest.write_text(
        "runs:\n  using: composite\n  steps:\n    - uses: owner/action@main\n",
        encoding="utf-8",
    )
    (finding,) = checker.scan(tmp_path)
    assert finding.path == manifest
    assert "not a full 40-hex commit SHA" in finding.problem


def test_local_reference_with_a_clean_manifest_is_exempt(tmp_path: Path) -> None:
    _write_workflow(tmp_path, "jobs:\n  a:\n    steps:\n      - uses: ./ci/local\n")
    manifest = tmp_path / "ci" / "local" / "action.yml"
    manifest.parent.mkdir(parents=True)
    manifest.write_text(
        f"runs:\n  using: composite\n  steps:\n    - uses: owner/action@{_SHA} # v1.0.0\n",
        encoding="utf-8",
    )
    assert checker.scan(tmp_path) == []


def test_local_reusable_workflow_file_is_exempt(tmp_path: Path) -> None:
    _write_workflow(tmp_path, "jobs:\n  a:\n    uses: ./.github/workflows/reusable.yml\n")
    _write_workflow(tmp_path, "jobs:\n  b:\n    steps:\n      - run: echo ok\n", name="reusable.yml")
    assert checker.scan(tmp_path) == []


@pytest.mark.parametrize(
    "reference",
    ["./ci/missing", "./../outside"],
    ids=["no-manifest", "escapes-the-repository"],
)
def test_unresolvable_local_reference_fails(tmp_path: Path, reference: str) -> None:
    _write_workflow(tmp_path, f"jobs:\n  a:\n    steps:\n      - uses: {reference}\n")
    (finding,) = checker.scan(tmp_path)
    assert "no scannable target" in finding.problem


def test_uses_named_input_is_deliberately_rejected(tmp_path: Path) -> None:
    # An action input literally named `uses` is treated as a reference and
    # rejected. Deliberate: a context-free rule leaves no nesting game to hide
    # a real reference in, at the cost of forbidding that input name here.
    body = (
        "jobs:\n  a:\n    steps:\n"
        f"      - uses: actions/checkout@{_SHA} # v6.0.2\n"
        "        with:\n"
        "          uses: something@v4\n"
    )
    (finding,) = _scan_snippet(tmp_path, body)
    assert "not a full 40-hex commit SHA" in finding.problem


def test_repo_tree_is_clean() -> None:
    findings = checker.scan(_REPO_ROOT)
    formatted = [f"{f.path.name}:{f.line}: {f.problem}" for f in findings]
    assert not formatted, "\n".join(formatted)


def test_scanner_sees_every_uses_the_yaml_parser_sees() -> None:
    assert sorted(_WORKFLOW_DIR.glob("*.y*ml")), "no workflow files found"

    findings = checker.verify_completeness(_REPO_ROOT)
    formatted = [f"{f.path.name}: {f.problem}" for f in findings]
    assert not formatted, "\n".join(formatted)

    # The walker itself must see the tree's pins, or the comparison above is
    # trivially empty-vs-empty.
    entries = checker.yaml_uses_entries(
        (_WORKFLOW_DIR / "action-pins.yml").read_text(encoding="utf-8")
    )
    assert entries, "the YAML walker found no uses: values at all"


def test_verification_fails_on_a_shape_the_line_scan_cannot_see(tmp_path: Path) -> None:
    _write_workflow(
        tmp_path,
        "jobs:\n  a:\n    steps:\n      - { uses: actions/checkout@v4 }\n",
        name="evasive.yml",
    )
    assert checker.scan(tmp_path) == [], "the line scan is expected to miss a flow mapping"
    (finding,) = checker.verify_completeness(tmp_path)
    assert "disagree" in finding.problem


def test_verification_fails_when_the_scan_sees_more_than_the_parser(tmp_path: Path) -> None:
    _write_workflow(
        tmp_path,
        "jobs:\n  a:\n    steps:\n      - run: |\n          uses: actions/foo@v1\n",
        name="heredoc.yml",
    )
    findings = checker.verify_completeness(tmp_path)
    assert any("disagree" in f.problem for f in findings)


def test_equal_values_at_different_lines_do_not_cancel(tmp_path: Path) -> None:
    # A compliant-looking decoy inside a run block (the scan sees it, the parse
    # does not) must not excuse a flow-mapped real reference (the parse sees it,
    # the scan does not), even though both carry the same value.
    body = (
        "jobs:\n  a:\n    steps:\n"
        f"      - {{ uses: actions/checkout@{_SHA} }}\n"
        "      - run: |\n"
        f"          uses: actions/checkout@{_SHA} # v6.0.2\n"
    )
    _write_workflow(tmp_path, body, name="cancel.yml")
    findings = checker.verify_completeness(tmp_path)
    assert any("disagree" in f.problem for f in findings)


# The gate's protection is split between the script and this wiring: the judge
# comes from the base branch, the PR's files arrive as data, and the check runs
# with completeness verification over the whole head. Asserted as parsed units
# bound to their steps rather than as substrings, so swapping the two
# checkouts' refs — or moving `path` or `persist-credentials` to the wrong one
# — fails here instead of leaving every fragment innocently present.
def test_action_pins_workflow_wires_the_checker() -> None:
    parsed = yaml.safe_load((_WORKFLOW_DIR / "action-pins.yml").read_text(encoding="utf-8"))

    # PyYAML reads the bare `on:` key as boolean True.
    triggers = parsed.get("on", parsed.get(True))
    assert "pull_request_target" in triggers

    steps = parsed["jobs"]["action-pins"]["steps"]
    checkouts = [s for s in steps if str(s.get("uses", "")).startswith("actions/checkout@")]
    assert len(checkouts) == 2

    judges = [s for s in checkouts if "path" not in s["with"]]
    data = [s for s in checkouts if s["with"].get("path") == "pr-head"]
    assert len(judges) == 1 and len(data) == 1

    assert judges[0]["with"]["ref"] == "${{ github.event.pull_request.base.ref }}"
    assert data[0]["with"]["ref"] == "${{ github.event.pull_request.head.sha }}"
    assert data[0]["with"]["persist-credentials"] is False

    runs = [s["run"].strip() for s in steps if "run" in s]
    assert "pip install -r requirements-test.txt" in runs
    assert "python .github/scripts/check_action_pins.py --annotate --verify-completeness pr-head" in runs


def test_symlinked_manifest_outside_the_repository_fails(tmp_path: Path) -> None:
    # `is_file` follows symlinks, so the boundary check must run on the resolved
    # manifest — a link pointing outside the repository fails the reference
    # instead of exempting content the gate never scans.
    repo = tmp_path / "repo"
    _write_workflow(repo, "jobs:\n  a:\n    steps:\n      - uses: ./ci/local\n")
    outside = tmp_path / "outside.yml"
    outside.write_text("runs:\n  using: composite\n  steps: []\n", encoding="utf-8")
    link_dir = repo / "ci" / "local"
    link_dir.mkdir(parents=True)
    try:
        (link_dir / "action.yml").symlink_to(outside)
    except OSError:
        pytest.skip("symlinks are unavailable on this platform")
    (finding,) = checker.scan(repo)
    assert "no scannable target" in finding.problem


def test_annotations_escape_pr_controlled_newlines(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    # A double-quoted YAML value can smuggle a newline into finding text; the
    # annotation must stay one inert workflow command, and the plain diagnostic
    # one physical line.
    _write_workflow(tmp_path, 'jobs:\n  a:\n    steps:\n      - uses: "foo\\nbar"\n')
    assert checker.main([str(tmp_path), "--annotate", "--verify-completeness"]) == 1
    output = capsys.readouterr()
    assert "%0A" in output.out
    assert "foo\nbar" not in output.out
    assert "foo\nbar" not in output.err


def test_main_exit_codes(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    clean = tmp_path / "clean"
    _write_workflow(
        clean,
        f"jobs:\n  a:\n    steps:\n      - uses: actions/checkout@{_SHA} # v6.0.2\n",
        name="ok.yml",
    )
    assert checker.main([str(clean)]) == 0

    dirty = tmp_path / "dirty"
    _write_workflow(
        dirty,
        "jobs:\n  a:\n    steps:\n      - uses: actions/checkout@v4\n",
        name="bad.yml",
    )
    assert checker.main([str(dirty), "--annotate"]) == 1
    output = capsys.readouterr()
    assert "not a full 40-hex commit SHA" in output.err
    assert "::error file=" in output.out

    evasive = tmp_path / "evasive"
    _write_workflow(
        evasive,
        "jobs:\n  a:\n    steps:\n      - { uses: actions/checkout@v4 }\n",
        name="flow.yml",
    )
    assert checker.main([str(evasive)]) == 0, "without verification the flow mapping goes unseen"
    assert checker.main([str(evasive), "--verify-completeness"]) == 1

    assert checker.main([str(tmp_path / "missing")]) == 2
