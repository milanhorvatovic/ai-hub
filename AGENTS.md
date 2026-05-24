# Agent instructions

## Project

ai-hub is a repository of AI-agnostic artifacts — primarily **skills** under `skills/<name>/`. Each skill is documentation (markdown): an always-loaded `SKILL.md` router, optional `capabilities/<name>/capability.md` files, and shared `references/`. Some skills also ship Python under `scripts/` (stdlib-only). Structural self-tests live at `tests/skills/<name>/`.

## Setup & tests

- Setup: `python -m venv venv && ./venv/bin/pip install -r requirements-test.txt`
- Test: `./venv/bin/pytest -q`
- Lint: `ruff check` (config in `pyproject.toml`) runs in CI on every PR; `prettier --check '**/*.md'` is opt-in

## Conventions

- **Markdown:** Prettier with `proseWrap: never` (`.prettierrc.json`) — author prose as one line per paragraph; never hard-wrap. `embeddedLanguageFormatting: off` keeps code inside fenced blocks (e.g. GitHub-Actions `${{ }}` examples) intact.
- **Skills are decoupled:** a skill never references another skill by name; express relationships as concepts.
- **Capabilities declare their own `allowed-tools`;** a router's `allowed-tools` is the union of its capabilities'.
- **Tests are stdlib-only** and validate on-disk shape (frontmatter, semver, capability/reference resolution) — keep them passing for any skill-shape change.
- **Commits / PR titles:** [Conventional Commits](https://www.conventionalcommits.org/), scope = skill name (`fix(git-toolkit): …`) or a repo area (`release`, `repo`, `deps`, `ci`); imperative ≤72 chars; author-only — no **attribution** trailers (`Co-Authored-By`, `Signed-off-by`). PRs are squash-merged, so the PR title is the subject release-please parses — a CI gate validates it.
- **Versioning:** per-skill SemVer in `SKILL.md` `metadata.version`; bump it for behavior-affecting changes (not internal-only edits). release-please cuts per-skill `<skill>-v<x.y.z>` releases; to override a computed bump, put a `Release-As: x.y.z` footer in the **squash commit message** (a release-please control footer, not an attribution trailer — the "no trailers" rule above is about attribution). See `docs/adr/0001-release-and-versioning.md`.

## Don't

- Don't hard-wrap prose or introduce a line-width limit.
- Don't add a skill-to-skill dependency or reference.
- Don't auto-apply repo settings or auto-publish; propose commands.
