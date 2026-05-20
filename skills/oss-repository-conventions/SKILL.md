---
name: oss-repository-conventions
description: >
  Scans a repository in one pass to extract and summarize its conventions —
  commit and PR format, branch naming, code style, test patterns, CI/CD,
  release process, security policies — by reading agent-instruction files,
  contributor guides, lint configs, templates, CODEOWNERS, workflow YAML, and
  related sources. Outputs a structured markdown summary grouped by domain
  with file-of-truth citations and flags conflicts between sources. Does not
  enforce, teach, or modify conventions — only reports what the repo already
  declares. Triggers when the user asks "what are this repo's conventions",
  "summarize git / PR / code conventions", "first-touch on this repo", "what
  should I know before contributing", "onboarding to this codebase", or wants
  a one-shot scan to bootstrap context for other work.
allowed-tools: Bash Read Grep
metadata:
  version: "0.1.0"
---

# oss-repository-conventions

## Purpose

Reports what conventions a repository declares — across git, PRs, code style, tests, CI, releases, and security — by reading the files that define them.

## What this skill is and is not

- **Is:** a one-pass scanner that gathers convention-declaring files, parses them, and outputs a structured summary.
- **Is not:** an enforcer (lint tools do that), a teacher (the docs do that), or a writer (the maintainers do that).

The output is a snapshot meant to bootstrap context for other work (e.g. feeding a commit/PR authoring tool, code review, or contributor onboarding) — not a source of truth itself.

## When to trigger

- "What are this repo's conventions?"
- "Summarize git / PR / code conventions"
- "First-touch on this repo — what should I know?"
- "Scan the repo for me"
- "Onboarding to this codebase"
- Before starting work on an unfamiliar repo
- Before configuring tooling (CI, linters, hooks) that needs to respect existing conventions

Do not trigger when:
- The user wants to *change* conventions (that's authoring docs, not scanning).
- The user wants to enforce conventions on a specific file (use the lint tools).
- The user wants to write commits/PRs that follow the conventions (that's a commit/PR authoring task, not a scan).

## Workflow

### 1. Locate the repo root

```
git rev-parse --show-toplevel
```

If not in a git repo → stop with "not a git repository; nothing to scan."

### 2. Discover convention-declaring files

Check every path in `references/convention-files.md` with a fast existence check. Don't read yet — just enumerate what's present. This is the inventory.

Bucket by domain:

| Domain | Source files (see reference for full list) |
|---|---|
| Agent / contributor instructions | `CLAUDE.md`, `AGENTS.md`, `.github/copilot-instructions.md`, `CONTRIBUTING.md` |
| Commit format | `.commitlintrc*`, `commitlint.config.*`, `.czrc`, `.gitlint`, `.gitmessage`, `commitizen.toml` |
| PR / issue | `.github/PULL_REQUEST_TEMPLATE*`, `.github/ISSUE_TEMPLATE/*`, `.github/CODEOWNERS` |
| Code style | `.editorconfig`, lint configs per language, formatter configs, `.pre-commit-config.yaml` |
| Tests | `pytest.ini`, `jest.config.*`, `vitest.config.*`, framework-specific configs |
| CI/CD | `.github/workflows/*.yml`, `.gitlab-ci.yml`, `.circleci/config.yml`, `Jenkinsfile` |
| Releases | `CHANGELOG.md`, `release-please-config.json`, `.semantic-release*`, `RELEASE.md` |
| Security | `SECURITY.md`, `.github/SECURITY.md`, `.github/dependabot.yml`, `.gitleaks.toml` |
| License | `LICENSE`, `LICENSE.md`, `LICENSE.txt` |

### 3. Read and parse the present files

For each present file, extract the rules it declares:

- **Lint configs** — extract the configured rules (max-line-length, naming, etc.) — surface the values, not the whole config.
- **Templates** — extract section headings, required fields.
- **Agent-instruction files** (`CLAUDE.md`, etc.) — read fully but report only convention-relevant sections (skip workflow descriptions and architectural docs).
- **CHANGELOG** — sample the first 1-2 release entries to infer format (Keep-a-Changelog vs custom).
- **CODEOWNERS** — list path-to-owner mappings, not the full content.
- **CI workflows** — list names + triggers, not the full step list.

For things that aren't in any file (e.g. branch naming when no doc declares it), **infer from git history**:

- Branch naming: `git branch -a --sort=-committerdate | head -30` — detect dominant prefix pattern.
- Commit-message style: `git log --pretty=format:'%s' -20` — detect conventional-commits, capitalization, length distribution.
- Merge mode: `gh api repos/{owner}/{repo} --jq '{squash, sm, rebase, merge}'` — when `gh` is available.

Mark inferred conventions explicitly: `(inferred from git history, not declared in any file)`.

### 4. Detect conflicts and gaps

While parsing, track:

- **Conflicts** — two sources declare the same convention differently (e.g. `CLAUDE.md` says ≤50-char subjects but `.commitlintrc.js` allows 72).
- **Gaps** — a convention is inferred but not documented (e.g. branch naming followed in practice but not in `CONTRIBUTING.md`).
- **Stale references** — `CONTRIBUTING.md` mentions a file or tool that no longer exists.

### 5. Output

```markdown
# <repo-name> conventions (inferred)

Scanned <YYYY-MM-DD>, <N> source files.

## Git & commits

- **Commit subject format:** <format>. Source: `<file>`.
- **Subject max length:** <N> chars. Source: `<file>`.
- **Body wrap:** <N> chars. Source: `<file>`.
- **Sign-off required:** Yes / No. Source: `<file>`.
- **Branch naming:** `<prefix>/...`. (inferred from git history; not documented)
- **Trailers required / preserved:** <list>. Source: `<file>`.

## PRs

- **Template:** `<path>`. Sections: <list>.
- **Required reviewers:** <summary from CODEOWNERS, e.g. "areas/api → @api-team">.
- **Merge methods enabled:** <list>. Source: `gh api`.
- **Squash commit message source:** <PR_BODY | PR_TITLE | COMMIT_MESSAGES | BLANK>.

## Code style

- **<Language>:** <tool> (config in `<file>`). Key rules: <line length>, <other>.
- **Pre-commit:** `<file>` runs <tools>.

## Tests

- **Framework:** <name> (config in `<file>`). Test file pattern: `<pattern>`.
- **Coverage:** <tool, target if stated>.

## CI/CD

- **Workflows:** <count> active (<names>).
- **CI triggers:** <push events, PR events>.

## Releases

- **Tool:** <release-please | semantic-release | manual | none>.
- **Changelog format:** <Keep-a-Changelog | custom | none>. Source: `<file>`.

## Security

- **Policy:** `<file>` (contact: <email or process>).
- **Dependabot:** <enabled for ...> / Not configured.
- **Secret scanning:** <tool> / Not configured.

## License

- **License:** <SPDX identifier>. Source: `<file>`.

## Conflicts and gaps

- [CONFLICT] `<file-A>` says <X> but `<file-B>` says <Y>.
- [GAP] <convention> followed in practice but not documented in any file.
- [STALE] `<file>` references `<missing-file>` which no longer exists.
```

If a domain has no convention-declaring files AND nothing inferable, omit the section entirely (don't write empty sections). Note in a "Missing domains" line at the bottom.

### 6. Length and output handling

- The full summary is typically 50-200 lines depending on repo size.
- For very large monorepos (>20 lint configs, >50 workflow files), summarize at the directory level rather than per-file.
- Write to `mktemp` AND show inline so the user can save it (e.g. paste into `CLAUDE.md` or repo notes).

## Edge cases

- **Subrepos / submodules** — scan only the current repo. Note submodules exist but don't recurse.
- **Monorepo with per-package configs** — surface the root-level conventions and note "per-package overrides may exist in <directories>".
- **No git history yet (initial commit only)** — skip the inferred-from-history items; report what files declare.
- **Fork checkouts** — scan the fork's local files; note that `gh api` merge-policy reflects the fork's settings, which may differ from upstream.
- **Private repos with limited `gh` scope** — degrade gracefully; report "merge policy unknown" rather than stopping.
- **Repo with conflicting agent-instruction files** (e.g. `CLAUDE.md` says X, `AGENTS.md` says Y) — surface both as a CONFLICT.

## Anti-patterns

- Don't dump full file contents — extract the rules, summarize.
- Don't infer aggressively when no signal exists — if branch naming has no pattern, say "no consistent pattern detected" rather than guessing.
- Don't recommend changes to the conventions — this skill reports, doesn't advise. (Advice is a separate task; suggest the user invoke a different skill or do it manually.)
- Don't conflate "convention not declared" with "convention not followed" — silence in config files doesn't mean the team has no convention; it may be tribal knowledge.
- Don't re-scan on every invocation if the result was already produced this session unless the user asks for a refresh (cache mentally, not on disk).
- Don't ship the summary as authoritative — always frame as "inferred / declared" with file citations so the user can verify.

## Output relationship to other work

This skill's output is *input* for other work:

- Commit/PR authoring tools read the same convention-declaring files internally (commit format, PR template, etc.). This skill summarizes them for human use; an authoring tool reads them for machine use. They don't share code, but they share sources.
- The summary can be pasted into `CLAUDE.md` or repo notes to make the conventions discoverable to future agent sessions.
- For onboarding contributors, the summary plus `CONTRIBUTING.md` together cover most "how do I work here" questions.
