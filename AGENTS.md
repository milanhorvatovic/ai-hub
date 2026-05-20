# Agent instructions

## Project

ai-hub is a repository of AI-agnostic artifacts — primarily **skills** under `skills/<name>/`. Each skill is documentation (markdown): an always-loaded `SKILL.md` router, optional `capabilities/<name>/capability.md` files, and shared `references/`. Some skills also ship Python under `scripts/` (stdlib-only). Structural self-tests live at `tests/skills/<name>/`.

## Setup & tests

- Setup: `python -m venv venv && ./venv/bin/pip install -r requirements-test.txt`
- Test: `./venv/bin/pytest -q`
- Lint (opt-in): `ruff check` (config in `pyproject.toml`); `prettier --check '**/*.md'`

## Conventions

- **Markdown:** Prettier with `proseWrap: never` (`.prettierrc.json`) — author prose as one line per paragraph; never hard-wrap. `embeddedLanguageFormatting: off` keeps code inside fenced blocks (e.g. GitHub-Actions `${{ }}` examples) intact.
- **Skills are decoupled:** a skill never references another skill by name; express relationships as concepts.
- **Capabilities declare their own `allowed-tools`;** a router's `allowed-tools` is the union of its capabilities'.
- **Tests are stdlib-only** and validate on-disk shape (frontmatter, semver, capability/reference resolution) — keep them passing for any skill-shape change.
- **Commits:** author-only (no `Co-Authored-By` / trailers); imperative subjects ≤72 chars. PRs are squash-merged.

## Don't

- Don't hard-wrap prose or introduce a line-width limit.
- Don't add a skill-to-skill dependency or reference.
- Don't auto-apply repo settings or auto-publish; propose commands.
