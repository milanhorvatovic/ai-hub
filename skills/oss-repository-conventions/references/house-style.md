# Maintainer house style

Conventions distilled from the maintainer's existing OSS repositories. When the generic OSS baseline offers several equally-valid options, `audit` recommends the house pattern so a new repo matches the rest of the fleet. The repo's own declared conventions still win over this file (see the router's precedence rule); this is the tie-breaker, not an override.

> Keep this file evidence-based. When a pattern here stops matching the maintainer's repos, update it — don't let it ossify into folklore.

## Observed patterns

Seen consistently across the more-developed repos (e.g. the GitHub Action and the skill-system repos):

| Area | House pattern |
| --- | --- |
| License | A real `LICENSE` with a clear SPDX id at repo root (the fleet's recurring weak spot — several repos still ship none; treat absence as `must`). |
| Readme | `README.md` with a one-line what-it-is, install, and usage up top. |
| Changelog | `CHANGELOG.md` in Keep-a-Changelog shape, kept in the repo (not only GitHub Releases). |
| Contributing | `CONTRIBUTING.md` at root. |
| Ownership | `.github/CODEOWNERS`. |
| PR template | `.github/PULL_REQUEST_TEMPLATE.md`. |
| Security | `.github/SECURITY.md` (present on the most-mature repo; missing on most — the gap to close). |
| Dependencies | `.github/dependabot.yaml` (note: `.yaml`, not `.yml`). |
| Release notes | `.github/RELEASE_NOTES_TEMPLATE.md` drives release prose. |
| Agent instructions | `AGENTS.md` + `CLAUDE.md` at root and `.github/copilot-instructions.md` (often `.github/instructions/` too) — the repo is set up for agent contributors. |
| Tool pinning | `mise.toml` for toolchain pinning (JS/TS); `.python-version` + `requirements-dev.txt` + `.coveragerc` (Python). |
| Repo hygiene | `.gitignore` and `.gitattributes` both present. |
| CI layout | `.github/workflows/` plus supporting `.github/scripts/`, `.github/instructions/`, sometimes `.github/actions/`. |
| Docs/extras | `docs/`, `examples/`, `scripts/`, `.markdown-link-check.json`. |

## Recurring gaps to flag

These are missing across most of the fleet — audit should surface them by default and offer to scaffold:

- **No `CODE_OF_CONDUCT.md`** anywhere — adopt Contributor Covenant.
- **Missing `LICENSE`** on several repos — pick and add one.
- **No `SECURITY.md`** on most repos — add a disclosure policy.
- **No issue templates / issue forms** under `.github/ISSUE_TEMPLATE/`.
- **Low GitHub community-profile health** (several repos sit at ~42%).

## House defaults (use when the repo is silent)

- License: prefer a permissive SPDX license consistent with the repo's siblings unless the maintainer states otherwise; confirm before writing.
- Changelog: Keep a Changelog + SemVer headings.
- Code of conduct: Contributor Covenant (latest), with a real enforcement contact, kept at repo root.
- Dependency automation: Dependabot via `.github/dependabot.yaml`.
- Agent-instruction files: `AGENTS.md` as the canonical source; `CLAUDE.md` / `.github/copilot-instructions.md` as tool-specific pointers.
