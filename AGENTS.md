# Agent instructions

## Project

ai-hub is a repository of AI-agnostic artifacts — primarily **skills** under `skills/<name>/`. Each skill is documentation (markdown): an always-loaded `SKILL.md` router, optional `capabilities/<name>/capability.md` files, and shared `references/`. Some skills also ship Python under `scripts/` (stdlib-only). A generic structural suite at `tests/skills/test_structure_all.py` validates every skill; per-skill content contracts live at `tests/skills/<name>/`. Description-activation corpora live at `tests/skill-corpus/<name>/skill.json`; after editing a `SKILL.md` description, review the corpus and refresh its `description_sha256` with the foundry evaluator's `--backfill-hash` (the `description-eval` workflow blocks on a stale hash).

## Setup & tests

- Setup: `python -m venv venv && ./venv/bin/pip install -r requirements-test.txt`
- Test: `./venv/bin/pytest -q`
- Lint: `ruff check` (config in `pyproject.toml`) runs in CI on every PR; `prettier --check '**/*.md'` is opt-in
- Hooks (opt-in, recommended for agents): `git config core.hooksPath .githooks` — rejects a rule-breaking commit message at commit time with the same linter CI runs, so violations surface as same-turn feedback instead of a red check later (`.githooks/pre-commit` delegates to `pre-commit` when installed, so skip `pre-commit install`)

## Conventions

- **Markdown:** Prettier with `proseWrap: never` (`.prettierrc.json`) — author prose as one line per paragraph; never hard-wrap. `embeddedLanguageFormatting: off` keeps code inside fenced blocks (e.g. GitHub-Actions `${{ }}` examples) intact.
- **Skills are decoupled:** a skill never references another skill by name; express relationships as concepts.
- **Capabilities declare their own `allowed-tools`;** a router's `allowed-tools` is the union of its capabilities'.
- **Tests are stdlib-only** and validate on-disk shape (frontmatter, semver, capability/reference resolution) — keep them passing for any skill-shape change.
- **Commits / PR titles:** [Conventional Commits](https://www.conventionalcommits.org/), scope = skill name (`fix(git-toolkit): …`) or a repo area (`release`, `repo`, `deps`, `ci`); imperative ≤72 chars, no trailing period; author-only — no **attribution** trailers (`Co-Authored-By`, `Signed-off-by`). PRs are squash-merged, so the PR title is the subject release-please parses — a CI gate validates it. Bot-authored titles (Dependabot and friends) waive the length cap only — their grouped-update suffix can exceed it — but still must parse as a Conventional Commit with a valid type and scope.
- **Commit bodies:** flowing why-narrative paragraphs, each exactly one source line (the `proseWrap: never` rule applied to commit text) — never hard-wrap; bullet lists, fenced and tab/4-space-indented blocks, and the trailer block are exempt. Squash-merge concatenates branch-commit bodies into main's permanent history, so the same CI gate lints every branch commit and the PR body.
- **No private planning references:** commit and PR text never cites internal planning codes, ticket paths, or audit documents — describe the change on its own terms. The CI gate rejects a narrow denylist of known markers.
- **Versioning:** per-skill SemVer in `SKILL.md` `metadata.version`; bump it for behavior-affecting changes (not internal-only edits). release-please cuts per-skill `<skill>-v<x.y.z>` releases; to override a computed bump, put a `Release-As: x.y.z` footer in the **squash commit message** (a release-please control footer, not an attribution trailer — the "no trailers" rule above is about attribution). See `docs/adr/0001-release-and-versioning.md`.

## Don't

- Don't hard-wrap prose or introduce a line-width limit.
- Don't add a skill-to-skill dependency or reference.
- Don't auto-apply repo settings or auto-publish; propose commands.
