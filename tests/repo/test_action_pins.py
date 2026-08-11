"""Unit and tree-level tests for the action-pin checker (`.github/scripts/check_action_pins.py`).

The checker scans workflow text line by line because the trailing-comment rule
lives in comments, which a YAML parser drops. That leaves one hole — a `uses:`
written in a shape the line regex does not match — so the cross-check test here
parses every workflow with PyYAML and asserts the scanner saw every `uses:`
value the parser sees.
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


def _scan_snippet(tmp_path: Path, body: str) -> list:
    (tmp_path / "sample.yml").write_text(body, encoding="utf-8")
    return checker.scan(tmp_path)


@pytest.mark.parametrize(
    "step",
    [
        f"      - uses: actions/checkout@{_SHA} # v6.0.2\n",
        f'      - uses: "actions/checkout@{_SHA}" # v6.0.2\n',
        f"      - uses: github/codeql-action/init@{_SHA} # v4.37.4\n",
        f"      - uses: actions/checkout@{_SHA} # 6.0.2\n",
        f"      - uses: owner/repo/.github/workflows/reusable.yml@{_SHA} # v1.2.3\n",
        "      - uses: ./.github/actions/local-action\n",
        "      - uses: docker://alpine@sha256:c5b1261d6d3e43071626931fc004f70149baeba2c8ec672bd4f27761f8e1ad6b\n",
    ],
    ids=[
        "sha-with-trailing-version",
        "quoted-value",
        "action-subpath",
        "bare-version-token",
        "reusable-workflow-sha",
        "local-action-exempt",
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
        ("      - uses: docker://alpine:3.19\n", "pinned by digest"),
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


def test_repo_workflows_are_clean() -> None:
    findings = checker.scan(_WORKFLOW_DIR)
    formatted = [f"{f.path.name}:{f.line}: {f.problem}" for f in findings]
    assert not formatted, "\n".join(formatted)


def _yaml_uses_values(document: object) -> list[str]:
    """Every string under a `uses` key, at any depth of the parsed workflow."""
    values: list[str] = []
    if isinstance(document, dict):
        for key, value in document.items():
            if key == "uses" and isinstance(value, str):
                values.append(value)
            values.extend(_yaml_uses_values(value))
    elif isinstance(document, list):
        for item in document:
            values.extend(_yaml_uses_values(item))
    return values


def test_scanner_sees_every_uses_the_yaml_parser_sees() -> None:
    workflows = sorted(_WORKFLOW_DIR.glob("*.y*ml"))
    assert workflows, "no workflow files found"

    for workflow in workflows:
        parsed = yaml.safe_load(workflow.read_text(encoding="utf-8"))
        expected = sorted(_yaml_uses_values(parsed))
        scanned = sorted(u.value for u in checker.collect_uses(_WORKFLOW_DIR) if u.path == workflow)
        assert scanned == expected, f"{workflow.name}: line scan disagrees with the YAML parse"


def test_main_exit_codes(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    clean = tmp_path / "clean"
    clean.mkdir()
    (clean / "ok.yml").write_text(
        f"jobs:\n  a:\n    steps:\n      - uses: actions/checkout@{_SHA} # v6.0.2\n",
        encoding="utf-8",
    )
    assert checker.main([str(clean)]) == 0

    dirty = tmp_path / "dirty"
    dirty.mkdir()
    (dirty / "bad.yml").write_text(
        "jobs:\n  a:\n    steps:\n      - uses: actions/checkout@v4\n",
        encoding="utf-8",
    )
    assert checker.main([str(dirty), "--annotate"]) == 1
    output = capsys.readouterr()
    assert "not a full 40-hex commit SHA" in output.err
    assert "::error file=" in output.out

    assert checker.main([str(tmp_path / "missing")]) == 2
