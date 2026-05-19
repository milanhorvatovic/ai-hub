"""Tool catalog — single source of truth for formatter identity and behavior.

The `Tool` enum lists every formatter binary the skill knows about. The
`REGISTRY` maps each tool to a `CommandTemplate` describing its audit-mode
command, format-mode command, and which optional flags it supports
(--config / --prose-wrap). New tools are added here exclusively; downstream
modules iterate the registry rather than branching on tool identity.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Tool(str, Enum):
    MARKDOWNLINT_CLI2 = "markdownlint-cli2"
    MARKDOWNLINT = "markdownlint"
    PRETTIER = "prettier"
    MDFORMAT = "mdformat"
    DPRINT = "dprint"
    REMARK = "remark"
    YAMLLINT = "yamllint"  # complementary — lints YAML frontmatter + fenced YAML blocks


@dataclass(frozen=True)
class CommandTemplate:
    """Command-template + per-tool flag-support flags.

    `config_flag` is the argv prefix that precedes a config path — typically
    `("--config",)` or `("-c",)`. The skill appends the path as a separate
    argv element so tools that reject `--config=PATH` (notably
    markdownlint-cli2, which treats `--config=PATH` as a file glob) work
    correctly. `None` means the tool does not accept a config-path flag
    (mdformat reads config from cwd-upward; dprint and remark rely on
    tool-side config discovery).

    `unwrap_flag` is the literal flag to append when the caller asks for
    "no prose wrap"; `None` means the tool does not expose such a flag.
    """

    audit: tuple[str, ...]
    fmt: tuple[str, ...]
    config_flag: tuple[str, ...] | None = None
    unwrap_flag: str | None = None


# Both `.md` and `.markdown` extensions are in scope per SKILL.md
# section "Supported file types". Tools whose default invocation accepts
# an explicit glob list (markdownlint-cli2 / markdownlint / prettier /
# remark) get both extensions enumerated so `.markdown` files are not
# silently skipped on the default-glob path. mdformat (`.` recursive)
# and dprint (`dprint.json` includes) defer to their own config and so
# do not enumerate extensions here.
# Negative globs (`#<dir>`) align with discovery._SKIP_DIRS so the
# default-glob invocation skips the same set of directories the
# inventory pipeline skips. Without `#venv` / `#target` here, a repo
# whose `venv/` or `target/` isn't covered by .gitignore (or whose
# Python virtualenv isn't named .venv) would have markdownlint-cli2
# lint vendored docs under those directories, despite SKILL.md
# documenting the skip set as identical across both pipelines.
_MARKDOWNLINT_CLI2_GLOBS = (
    "**/*.md", "**/*.markdown",
    "#node_modules", "#.git", "#dist", "#build", "#.venv", "#venv", "#target",
)
_MARKDOWNLINT_GLOB = (
    "--ignore-path", ".gitignore", "**/*.md", "**/*.markdown",
)


REGISTRY: dict[Tool, CommandTemplate] = {
    Tool.MARKDOWNLINT_CLI2: CommandTemplate(
        audit=("markdownlint-cli2", *_MARKDOWNLINT_CLI2_GLOBS),
        fmt=("markdownlint-cli2", "--fix", *_MARKDOWNLINT_CLI2_GLOBS),
        config_flag=("--config",),
    ),
    Tool.MARKDOWNLINT: CommandTemplate(
        audit=("markdownlint", *_MARKDOWNLINT_GLOB),
        fmt=("markdownlint", "--fix", *_MARKDOWNLINT_GLOB),
        config_flag=("--config",),
    ),
    Tool.PRETTIER: CommandTemplate(
        audit=("prettier", "--check", "--parser", "markdown", "**/*.md", "**/*.markdown"),
        fmt=("prettier", "--write", "--parser", "markdown", "**/*.md", "**/*.markdown"),
        config_flag=("--config",),
        unwrap_flag="--prose-wrap=never",
    ),
    Tool.MDFORMAT: CommandTemplate(
        audit=("mdformat", "--check", "."),
        fmt=("mdformat", "."),
        unwrap_flag="--wrap=no",
    ),
    Tool.DPRINT: CommandTemplate(
        audit=("dprint", "check"),
        fmt=("dprint", "fmt"),
    ),
    Tool.REMARK: CommandTemplate(
        audit=("remark", "--quiet", "--frail", "**/*.md", "**/*.markdown"),
        fmt=("remark", "--output", "**/*.md", "**/*.markdown"),
    ),
}


SUPPORTED_TOOLS: tuple[Tool, ...] = (*REGISTRY.keys(), Tool.YAMLLINT)
"""All tools the skill orchestrates — formatters from REGISTRY plus yamllint
(which doesn't fit the audit/format command-template pattern; it has its own
stdin-based service in yaml_audit.py). Probe + recommend iterate this list."""
