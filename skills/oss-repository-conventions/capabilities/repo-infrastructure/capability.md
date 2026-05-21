---
name: repo-infrastructure
description: >
  Scans, audits, and scaffolds a repository's plumbing — the git hygiene files
  (.gitignore, .gitattributes, .editorconfig, .mailmap) and the GitHub repo
  settings (default branch name, description and topics, merge-button policy,
  auto-delete-branch, feature toggles). Audit flags a missing or stack-mismatched
  .gitignore and merge settings that contradict the repo's history policy;
  scaffold writes the hygiene files and proposes the gh commands for settings.
  Branch-protection *rules* belong to the security-policy capability. Triggers on
  "set up .gitignore/.gitattributes/.editorconfig", "fix repo settings",
  "configure the merge button", "add repo topics", or a full-repo audit.
allowed-tools: Bash Read Grep Glob Write Edit
---

# repo-infrastructure capability

Governs the repository's plumbing: the git hygiene files that keep the working tree and history clean, and the GitHub settings that shape how the repo behaves. Reads and judges by default; writes hygiene files on confirmation and _proposes_ (never applies) settings changes.

## Modes

- **scan** — report the hygiene files and repo settings present.
- **audit** — judge them against `../../references/oss-health-rubric.md`.
- **scaffold** — write hygiene files after confirmation; output `gh` commands for settings.

## Inputs & guards

- Not a git repo → stop.
- Branch-_protection_ rules (required reviews/checks, force-push) are security posture — defer to the security-policy capability; here, cover only general settings.
- Style _enforcement_ (linters/formatters) is the code-style capability; here, cover only `.editorconfig` presence as hygiene.
- Settings need `gh`; without it, mark settings checks `unknown — gh not available`.

## Languages

Detect per `../../references/language-support.md`. `.gitignore` scaffolding is bound to GitHub's gitignore template set:

- **First-class:** any name in `gh api /gitignore/templates` (Python, Node, Go, Rust, Swift, Objective-C, Ruby, Java, …) — fetched and merged.
- **Recognized:** stacks without a template — hand-assemble ignores from detected build / output / dependency directories.
- **Unknown:** ignore only the obvious local / secret paths; never fabricate stack-specific ignores.
- **Vendored marks:** mark vendored/build trees in `.gitattributes` (`node_modules/`, `vendor/`, `Pods/`, `.build/`, `target/`, `dist/`) as `linguist-vendored` / `linguist-generated` so they don't skew language detection or get linted.

## Scan

Sources (catalog: `../../references/convention-files.md`, Misc section), citing each:

1. Hygiene files: `.gitignore`, `.gitattributes`, `.editorconfig`, `.mailmap`.
2. `.gitignore` fit: does it cover this stack's build output, deps, and local/secret files (e.g. `node_modules/`, `__pycache__/`, `.env`, `dist/`)?
3. Settings (`gh`): default branch (`gh api repos/{owner}/{repo} --jq .default_branch`); description + topics; merge-button policy (`allow_squash_merge` / `allow_merge_commit` / `allow_rebase_merge`, `delete_branch_on_merge`); feature toggles (issues, wiki, projects).

## Audit

Checks follow the schema in `../../references/oss-health-rubric.md` (`id` — **severity** [· scorecard: Name]. criterion. why):

- `gitignore-present` — **should**. Fail when there's no `.gitignore`, or it omits this stack's build/secret paths. Without it, artifacts and secrets get committed.
- `gitattributes-present` — **could**. Pass when `.gitattributes` normalizes line endings and marks generated/vendored paths. Prevents CRLF churn and skewed language stats.
- `editorconfig-present` — **could**. Pass when `.editorconfig` sets baseline charset/whitespace. Keeps formatting consistent across editors before linters run.
- `default-branch-conventional` — **could**. Pass when the default branch is `main` (or a deliberate, documented alternative). Reduces surprise for contributors and tooling.
- `described-and-topics` — **could** (public repos). Pass when the repo has a description and topics. Drives discoverability.
- `merge-policy-consistent` — **could**. Pass when the merge-button settings match the repo's stated history policy (e.g. squash-only with branch auto-delete for a linear history). Mismatch produces history the project doesn't want.

## Scaffold

Hygiene files — write after confirmation:

- **`.gitignore`** — fetch a stack-appropriate base (`gh api /gitignore/templates/{name} --jq .source`, or github/gitignore) and add repo-specific paths. Append to an existing one via Edit; show the diff.
- **`.gitattributes`** / **`.editorconfig`** — from `references/scaffold-templates.md`, tailored to the languages present.

Settings — **propose, never apply**:

```bash
gh repo edit {owner}/{repo} --default-branch main \
  --enable-squash-merge --enable-merge-commit=false \
  --delete-branch-on-merge --add-topic <topic>
```

Show the command and what it changes; let the user run it.

## Output

Report per `../../references/output-format.md`: scan emits the hygiene + settings inventory with sources; audit emits severity-tagged findings, the domain score, and a `scaffold` offer or the exact `gh` command for each unmet check.

## Edge cases

- **Existing `.gitignore`** — extend, don't replace; never drop entries the repo already relies on.
- **Monorepo** — a root `.gitignore` plus per-package ones is normal; don't flag nested ignores as redundant.
- **Non-`main` default by intent** (e.g. `trunk`, `master` for compatibility) — honor a documented choice; only flag undocumented drift.
- **`gh` unavailable** — settings checks are `unknown`; still audit the on-disk hygiene files.

## Anti-patterns

- Don't apply repo settings automatically — output the `gh` command.
- Don't replace an existing `.gitignore`; append and show the diff.
- Don't duplicate branch-protection (security-policy) or style enforcement (code-style) here.
- Don't pass settings checks as satisfied when `gh` is unavailable — mark them `unknown`.
