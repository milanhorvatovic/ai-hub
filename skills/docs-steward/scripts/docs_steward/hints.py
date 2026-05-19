"""Per-tool install commands across platforms.

`install_hints(tool)` returns the list of installation commands the recommender
surfaces to the user; the user picks the line for their environment. The skill
never executes these — see the anti-install anti-pattern in SKILL.md.

Hints are tuples (not lists) so the data is immutable; callers that need a
list can `list(install_hints(tool))`.
"""

from __future__ import annotations

from .tools import Tool


_HINTS: dict[Tool, tuple[str, ...]] = {
    Tool.PRETTIER: (
        "npm install --global prettier             # canonical: via npm",
        "pnpm add -g prettier                      # alternative: via pnpm",
        "bun add -g prettier                       # alternative: via bun",
        "yarn global add prettier                  # alternative: via yarn (classic)",
        "volta install prettier                    # alternative: via volta",
        "mise use -g npm:prettier                  # alternative: via mise (npm backend)",
        "npx prettier@latest --version             # one-shot: via npx (no install)",
    ),
    Tool.MDFORMAT: (
        "pipx install mdformat                     # preferred: isolated via pipx",
        "uv tool install mdformat                  # alternative: via uv (fast)",
        "pip install --user mdformat               # alternative: user-site via pip",
        "brew install mdformat                     # macOS via Homebrew",
        "mise use -g pipx:mdformat                 # alternative: via mise (pipx backend)",
        "pipx install mdformat-gfm                 # extra: GitHub-flavored markdown plugin",
    ),
    Tool.MARKDOWNLINT_CLI2: (
        "npm install --global markdownlint-cli2    # canonical: via npm",
        "pnpm add -g markdownlint-cli2             # alternative: via pnpm",
        "bun add -g markdownlint-cli2              # alternative: via bun",
        "yarn global add markdownlint-cli2         # alternative: via yarn (classic)",
        "mise use -g npm:markdownlint-cli2         # alternative: via mise (npm backend)",
    ),
    Tool.MARKDOWNLINT: (
        "npm install --global markdownlint-cli     # canonical: via npm",
        "pnpm add -g markdownlint-cli              # alternative: via pnpm",
        "bun add -g markdownlint-cli               # alternative: via bun",
        "mise use -g npm:markdownlint-cli          # alternative: via mise (npm backend)",
    ),
    Tool.DPRINT: (
        "curl -fsSL https://dprint.dev/install.sh | sh   # POSIX: official installer",
        "iwr https://dprint.dev/install.ps1 -useb | iex  # Windows PowerShell installer",
        "brew install dprint                             # macOS via Homebrew",
        "winget install dprint                           # Windows via winget",
        "scoop install dprint                            # Windows via Scoop",
        "cargo install dprint                            # via Rust toolchain",
        "mise use -g aqua:dprint/dprint                  # alternative: via mise (aqua backend)",
    ),
    Tool.REMARK: (
        "npm install --global remark-cli remark-preset-lint-recommended    # canonical: via npm",
        "pnpm add -g remark-cli remark-preset-lint-recommended             # alternative: via pnpm",
        "bun add -g remark-cli remark-preset-lint-recommended              # alternative: via bun",
        "mise use -g npm:remark-cli                                        # alternative: via mise (npm backend, install preset separately)",
    ),
    Tool.YAMLLINT: (
        "pipx install yamllint                     # preferred: isolated via pipx",
        "uv tool install yamllint                  # alternative: via uv (fast)",
        "pip install --user yamllint               # alternative: user-site via pip",
        "brew install yamllint                     # macOS via Homebrew",
        "sudo apt install yamllint                 # Debian/Ubuntu via apt",
        "sudo dnf install yamllint                 # Fedora/RHEL via dnf",
        "mise use -g pipx:yamllint                 # alternative: via mise (pipx backend)",
    ),
}


def install_hints(tool: Tool) -> tuple[str, ...]:
    """Return install commands for `tool`; empty tuple if unknown."""
    return _HINTS.get(tool, ())
