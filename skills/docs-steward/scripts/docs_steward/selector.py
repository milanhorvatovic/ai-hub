"""Tool selection: from detected configs to a composite audit plan.

`build_audit_plan` turns the full set of detected baseline configs into an
`AuditPlan` — exactly one write-capable formatter owner plus an optional
read-only complementary lint pass, each carrying its own family's config.
Resolution is **per tool family**: the formatter concern uses the repo's
first formatter-family config (prettier / remark / mdformat / dprint) or
falls back to `UNIVERSAL_SUBSET` (bundled config); the lint concern uses the
repo's first markdownlint-family config or the bundled fallback. A config
from one family therefore never suppresses the check owned by another —
a repo declaring both `.markdownlint.json` and `.prettierrc` gets both
passes, each honoring its own file.

The baseline-preference table maps a baseline-name prefix to the ordered list
of tools that consume that config family. When the baseline matches a prefix,
the matching tools are tried in order; the first one on PATH wins. When no
prefix matches (or none of the preferred tools is available), `FALLBACK_ORDER`
is tried in order — prettier first, so a repo that declares no formatter
config still gets consistent formatting (including `proseWrap: never` from
the bundled config).

This selection order is intentionally different from `priority.INSTALL_PRIORITY`
which optimizes for "what should the user install first?" — see priority.py.
"""

from __future__ import annotations

import os.path
from collections.abc import Sequence
from dataclasses import dataclass

from .baseline import UNIVERSAL_SUBSET
from .process import ProcessRunner
from .tools import Tool

# `.markdownlint-cli2.{jsonc,yaml}` is a cli2-specific configuration
# format the legacy `markdownlint` CLI cannot parse. Match cli2 configs
# to CLI2 *only* — order is significant: this prefix must come BEFORE
# the broader `.markdownlint.` entry below, otherwise the broader
# prefix would also match the cli2 filename and `MARKDOWNLINT` would
# end up in the preferred-tools tuple, leading the runner to forward a
# cli2-only config to legacy markdownlint via `--config`.
# `.markdownlint.{json,jsonc,yaml,yml}` rule configs are consumed by
# both binaries, so that prefix keeps the CLI2 / MARKDOWNLINT pair.
_BASELINE_PREFERENCES: tuple[tuple[str, tuple[Tool, ...]], ...] = (
    (".markdownlint-cli2.", (Tool.MARKDOWNLINT_CLI2,)),
    (".markdownlint.", (Tool.MARKDOWNLINT_CLI2, Tool.MARKDOWNLINT)),
    (".prettierrc", (Tool.PRETTIER,)),
    ("prettier.config.", (Tool.PRETTIER,)),
    (".remarkrc", (Tool.REMARK,)),
    (".mdformat.toml", (Tool.MDFORMAT,)),
    ("dprint.json", (Tool.DPRINT,)),
)


FALLBACK_ORDER: tuple[Tool, ...] = (
    Tool.PRETTIER,
    Tool.MARKDOWNLINT_CLI2,
    Tool.MARKDOWNLINT,
    Tool.MDFORMAT,
    Tool.DPRINT,
    Tool.REMARK,
)


def _basename(baseline: str) -> str:
    """Cross-host basename. `os.path.basename` only treats backslashes as
    separators on Windows — on POSIX (including WSL / Git Bash / a POSIX
    Python invoked from CI against a Windows-style argument) a path like
    `C:\\repo\\.prettierrc` returns the entire string. Normalize
    backslashes to forward slashes first so the family-prefix match
    behaves identically on every host."""
    return os.path.basename(baseline.replace("\\", "/"))


def select_tool(baseline: str, runner: ProcessRunner) -> Tool | None:
    """Pick the tool to run for `baseline`. Returns None when no usable tool
    is on PATH for any preference + fallback path.

    Matching is done on the baseline's basename so an explicit
    `--baseline /repo/.prettierrc` (or `config/.prettierrc`) honours the
    same family preference as the auto-detected bare `.prettierrc`.
    Without the basename normalization, an absolute or subdirectory path
    fails the `startswith` check and silently falls through to
    `FALLBACK_ORDER`, picking whichever formatter happens to be on PATH
    first — frequently a different family than the user asked for.
    """
    basename = _basename(baseline)
    for prefix, preferred in _BASELINE_PREFERENCES:
        if basename.startswith(prefix):
            for tool in preferred:
                if runner.which(tool.value):
                    return tool
            break  # baseline matched a prefix but none of its tools were available
    for tool in FALLBACK_ORDER:
        if runner.which(tool.value):
            return tool
    return None


def baseline_belongs_to_tool(baseline: str, tool: Tool) -> bool:
    """True when `baseline` is a config the given `tool` natively consumes.

    Routes through the same `_BASELINE_PREFERENCES` table as `select_tool`
    so the answer agrees with selection: e.g. `.prettierrc` belongs to
    Tool.PRETTIER, `.markdownlint.json` belongs to Tool.MARKDOWNLINT_CLI2
    and Tool.MARKDOWNLINT, `.editorconfig` and `universal-subset` belong
    to no tool (the prefix table doesn't include them).

    Used by `runner.run_tool` to decide whether an explicit baseline path
    should be forwarded as the tool's `--config` argument. Passing a
    non-family config (e.g. `.editorconfig` to markdownlint) would either
    error out the formatter or be silently ignored, so the runner only
    threads `--config` through for family-matching baselines.
    """
    basename = _basename(baseline)
    for prefix, preferred in _BASELINE_PREFERENCES:
        if basename.startswith(prefix):
            return tool in preferred
    return False


LINT_TOOLS: tuple[Tool, ...] = (Tool.MARKDOWNLINT_CLI2, Tool.MARKDOWNLINT)
"""The markdownlint family — semantic `MD###` rule linters. In the audit
plan they run as the read-only complementary pass; every other markdown
tool in the registry is a write-capable formatter."""


def _family(baseline: str) -> tuple[Tool, ...] | None:
    """The tool family consuming `baseline`, or None for configs that belong
    to no markdown tool (`.editorconfig`, the `universal-subset` sentinel)."""
    basename = _basename(baseline)
    for prefix, preferred in _BASELINE_PREFERENCES:
        if basename.startswith(prefix):
            return preferred
    return None


def _is_lint_family(baseline: str) -> bool:
    family = _family(baseline)
    return family is not None and all(tool in LINT_TOOLS for tool in family)


def _is_formatter_family(baseline: str) -> bool:
    family = _family(baseline)
    return family is not None and not any(tool in LINT_TOOLS for tool in family)


@dataclass(frozen=True)
class PlannedPass:
    """One executable step of the audit plan: a tool plus the baseline that
    governs its config resolution (a repo config filename/path, or
    `UNIVERSAL_SUBSET` for the bundled fallback)."""

    tool: Tool
    baseline: str


@dataclass(frozen=True)
class AuditPlan:
    """Composite verification plan for one markdown run.

    `formatter` is the single write-capable owner — None only when no
    usable markdown tool is on PATH at all (`formatter_baseline` still
    names the config the owner would have used, so the caller can surface
    it in the missing-tool report). `linter` is the read-only complementary
    markdownlint pass — None when the owner already is a markdownlint
    binary (its own pass covers the rules) or when no markdownlint binary
    is on PATH (the pass is optional; soft skip).
    """

    formatter: PlannedPass | None
    formatter_baseline: str
    linter: PlannedPass | None


def build_audit_plan(
    detected: Sequence[str],
    runner: ProcessRunner,
    forced_baseline: str | None = None,
) -> AuditPlan:
    """Derive the audit plan from every detected baseline config.

    Per-family resolution: the formatter concern is governed by the first
    detected formatter-family config (else `UNIVERSAL_SUBSET`); the lint
    concern by the first detected markdownlint-family config (else
    `UNIVERSAL_SUBSET`). `forced_baseline` (the CLI's `--baseline`)
    replaces only the formatter owner's baseline — complementary passes
    stay derived from what the repo declares, so forcing a formatter never
    silently downgrades the lint pass to bundled rules. Forcing a
    markdownlint-family baseline makes markdownlint the owner (matching
    `select_tool`), and the complementary pass collapses into it.
    """
    if forced_baseline is not None:
        formatter_baseline = forced_baseline
    else:
        formatter_baseline = next(
            (b for b in detected if _is_formatter_family(b)), UNIVERSAL_SUBSET
        )
    owner_tool = select_tool(formatter_baseline, runner)
    formatter = (
        PlannedPass(owner_tool, formatter_baseline) if owner_tool is not None else None
    )

    if formatter is None or formatter.tool in LINT_TOOLS:
        return AuditPlan(formatter, formatter_baseline, linter=None)

    lint_tool = next((t for t in LINT_TOOLS if runner.which(t.value)), None)
    if lint_tool is None:
        return AuditPlan(formatter, formatter_baseline, linter=None)
    lint_baseline = next(
        (b for b in detected if _is_lint_family(b)), UNIVERSAL_SUBSET
    )
    return AuditPlan(
        formatter, formatter_baseline, linter=PlannedPass(lint_tool, lint_baseline)
    )
