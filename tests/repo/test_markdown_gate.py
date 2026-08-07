"""Structural contracts for the markdown format gate.

The gate is four cooperating files: a pin, a workflow that runs it, an ignore
file that keeps generated output out, and the declarations that tell a
contributor it blocks. Each assertion below is a failure that has a name — a
gate that runs on nothing, a gate that reddens every release PR, or a
declaration that outlives the rule it describes.
"""

import json
import re
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
_LINT_WORKFLOW = _REPO_ROOT / ".github" / "workflows" / "lint.yml"
_PACKAGE_JSON = _REPO_ROOT / "package.json"
_PACKAGE_LOCK = _REPO_ROOT / "package-lock.json"
_PRETTIER_IGNORE = _REPO_ROOT / ".prettierignore"
_PRE_COMMIT = _REPO_ROOT / ".pre-commit-config.yaml"
_DEPENDABOT = _REPO_ROOT / ".github" / "dependabot.yaml"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_prettier_is_pinned_to_an_exact_version() -> None:
    """A range would let CI and a contributor's hook resolve different versions."""
    declared = json.loads(_read(_PACKAGE_JSON))["devDependencies"]["prettier"]

    assert re.fullmatch(r"\d+\.\d+\.\d+", declared), (
        f"prettier is declared as {declared!r}; an exact version is what makes"
        " the hook and CI agree"
    )
    locked = json.loads(_read(_PACKAGE_LOCK))["packages"]["node_modules/prettier"]["version"]
    assert locked == declared, f"lockfile has prettier {locked}, package.json wants {declared}"


def test_lockfile_is_the_only_source_of_the_version() -> None:
    """A second literal version is a second thing to update, i.e. drift."""
    declared = json.loads(_read(_PACKAGE_JSON))["devDependencies"]["prettier"]

    for path in (_LINT_WORKFLOW, _PRE_COMMIT):
        assert f"prettier@{declared}" not in _read(path), (
            f"{path.name} names the prettier version literally; let `npm ci`"
            " read package-lock.json instead"
        )


def test_ci_installs_from_the_lockfile() -> None:
    # Read the commands the job runs, not the whole file: prose about
    # `npm install` is how the choice is explained, not how it is made.
    commands = re.findall(r"^\s*run:\s*(.+)$", _read(_LINT_WORKFLOW), flags=re.MULTILINE)

    assert "npm ci" in commands, "npm install may resolve a version the lockfile does not pin"
    assert not any(command.startswith("npm install") for command in commands)
    assert "npm run format:check" in commands


def test_hook_runs_the_pinned_binary() -> None:
    """`entry: prettier` would run whatever is on PATH, which is the drift."""
    hook = _read(_PRE_COMMIT)

    assert "npx --no-install prettier --write" in hook
    assert "entry: prettier" not in hook


@pytest.mark.parametrize(
    "path_filter",
    [
        "**/*.md",
        ".prettierrc.json",
        ".prettierignore",
        "package.json",
        "package-lock.json",
        ".nvmrc",
    ],
)
def test_push_filter_covers_the_gate_inputs(path_filter: str) -> None:
    """Absent from `paths:`, the job runs on pull requests and never on push to main.

    Matched as a list item with optional quoting: YAML accepts `- package.json`
    and `- "package.json"` alike, and which one is written is not this rule.
    """
    entry = re.compile(
        rf"""^\s*-\s*(?P<q>["']?){re.escape(path_filter)}(?P=q)\s*$""", re.MULTILINE
    )

    assert entry.search(_read(_LINT_WORKFLOW)), (
        f"{path_filter} is not in lint.yml's push paths: filter; a push touching"
        " only that file would skip the job it is an input to"
    )


def test_generated_changelogs_stay_out_of_the_gate() -> None:
    """release-please rewrites these every run, so no fix to them survives."""
    ignored = _read(_PRETTIER_IGNORE)

    assert "skills/*/CHANGELOG.md" in ignored
    assert not re.search(r"^CHANGELOG\.md$", ignored, flags=re.MULTILINE), (
        "the root CHANGELOG.md is hand-authored and stays under the gate"
    )


def test_node_toolchain_is_dependabot_visible() -> None:
    """An unwatched pin is the stale-version failure the pin exists to prevent."""
    assert "package-ecosystem: npm" in _read(_DEPENDABOT)


@pytest.mark.parametrize(
    "dev_config", ["package.json", "package-lock.json", ".nvmrc", ".prettierignore"]
)
def test_toolchain_files_are_export_ignored(dev_config: str) -> None:
    """These are repo machinery. Every other root dev config is export-ignored,
    so shipping these in a source archive would be the incoherent case: a
    consumer receiving the pin but not the config it pins a formatter for."""
    attributes = _read(_REPO_ROOT / ".gitattributes")

    assert re.search(rf"^/{re.escape(dev_config)}\s+export-ignore$", attributes, re.MULTILINE)


@pytest.mark.parametrize(("setting", "value"), [("proseWrap", "never"), ("embeddedLanguageFormatting", "off")])
def test_gate_enforces_the_convention_the_docs_state(setting: str, value: str) -> None:
    """Four documents name these settings. Changing one here and nowhere else
    leaves the gate enforcing a rule no declaration describes — green CI, four
    false statements. Changing the convention means changing them together."""
    config = json.loads(_read(_REPO_ROOT / ".prettierrc.json"))

    assert config.get(setting) == value, (
        f"{setting} is {config.get(setting)!r}, but the declarations say {value!r};"
        " update AGENTS.md, README.md, CONTRIBUTING.md and docs/adding-a-skill.md"
        " in the same change"
    )


@pytest.mark.parametrize(
    ("declaration", "must_contain"),
    [
        ("AGENTS.md", "npm run format:check"),
        ("README.md", "npm run format:check"),
        ("CONTRIBUTING.md", "npm run format:check"),
        ("docs/adding-a-skill.md", "npm run format"),
    ],
)
def test_declarations_name_the_gate(declaration: str, must_contain: str) -> None:
    """A convention change touches declaration and gate together, or the
    untouched surface keeps asserting the old rule."""
    text = _read(_REPO_ROOT / declaration)

    assert must_contain in text
    assert "is opt-in" not in text, f"{declaration} still calls the markdown check opt-in"
