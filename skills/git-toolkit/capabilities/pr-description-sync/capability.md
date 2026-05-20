---
name: pr-description-sync
description: >
  Reviews a pull request and decides whether its description (PR body / PR
  summary) still matches the branch — code, docs, config, tests, workflows.
  Fetches the body via gh, diffs the branch against its base (handling fork
  PRs, force-pushes, stacked PRs), maps description claims onto observed
  changes, scans for leaked secrets, classifies as IN-SYNC, MINOR-UPDATE, or
  MAJOR-REWRITE, and when updates are warranted produces a proposed new body
  plus the exact gh command — never auto-applies. Triggers on "check / sync /
  refresh / update / rewrite my PR description", "is my PR body still
  accurate", "the description feels stale", after large refactors or
  force-pushes, or before requesting review.
---

# pr-description-sync capability

Decides whether a PR description still reflects the branch and, if not, proposes a fix.

## When to trigger (vs `pr-description-write`)

- This capability: PR has a substantive existing body that needs validation.
- `pr-description-write`: PR body is empty / WIP / unfilled template.

This capability detects the empty/WIP/unfilled case internally and hands off to `pr-description-write` rather than fabricating a body.

## Inputs

Resolve the target PR in this order, stopping at the first that works:

1. PR number or URL the user provided.
2. PR associated with the current branch: `gh pr list --head <branch> --state all --json number,state,baseRefName,author`.
   - If **multiple open PRs** match → list them and ask the user which one.
   - If **only closed PRs** match and the user didn't specify → report and stop.
3. If none found → report no-PR and stop.

Guards before any work:

- **Forge detection** — run `git remote get-url origin` and classify per `../../references/forge-adapters.md`. Surface `forge=<x>; capability assumes GitHub gh by default` in the proposal preamble. On non-GitHub remotes (GitLab / Codeberg / Bitbucket), follow the degrade path in `forge-adapters.md` — refuse cleanly if no portable equivalent exists.
- **State guard** — if `state ∈ {MERGED, CLOSED}` → refuse; do not propose edits to a closed PR.
- **Bot guard** — if `author.login` matches a login pattern in `../../references/bot-signatures.md` (dependabot, renovate, github-actions, copilot, snyk, pre-commit-ci, etc.) → skip; bot-authored PR bodies are managed by the bot itself.
- **gh auth** — on auth failure from any `gh` call, stop and tell the user to run `gh auth login`.

## Workflow

### 1. Gather current state

**1a. Fetch PR metadata** (sequential — later steps need its fields):

```
gh pr view <num> --json number,url,title,body,baseRefName,headRefName,headRefOid,\
isDraft,state,additions,deletions,changedFiles,isCrossRepository,headRepository,\
headRepositoryOwner,baseRepository,author
```

**1b. Branch on repo topology.** Per `../../references/git-gh-quirks.md`:

- **Cross-repo / fork PR** → use remote-authoritative reads (`gh pr diff <num> --patch` + paginated files API). Local git can't see the head.
- **Same-repo PR** → parallel: `git fetch origin <baseRefName>` (graceful degrade), `git log --no-merges origin/<baseRefName>..HEAD`, `git diff --stat origin/<baseRefName>...HEAD`.

**1c. Reconcile local vs remote head.** Compare local `HEAD` to `headRefOid`. On divergence → discard same-repo local results and switch to cross-repo path. Details in `../../references/git-gh-quirks.md`.

### 1.5. Merge policy

`gh api repos/{owner}/{repo} --jq '{squash:.allow_squash_merge, sm:.squash_merge_commit_message, st:.squash_merge_commit_title, rebase:.allow_rebase_merge}'`.

Key rule: **`sm == "PR_BODY"` means the body IS the squash commit message** → shape MAJOR-REWRITE as a flat commit message. Full interpretation in `../../references/merge-policy.md`.

### 2. Inventory changes

Bucket each changed path (code / tests / docs / config / CI / assets / infra / schema / deps). Sample **deterministically**: largest file (most likely substantive) + most-recently-modified file (closest to current intent) per bucket. Skip binaries — infer from path + commit subjects. When sampling is used (>~50 files), record "sampled" in the verdict.

### 3. Parse the description

Extract structural claims: Summary / Changes / Test plan / Screenshots / Migration notes / Linked issues. If empty / WIP / one-liner → treat as MAJOR-REWRITE and hand off to `pr-description-write` (don't author the body in this capability — that's `pr-description-write`'s job).

**Detect unfilled PR template** per `../../references/pr-template-detection.md` — strip HTML comments, compute overlap, >60% → MAJOR-REWRITE → hand off to `pr-description-write`.

**Classify each issue reference** per `../../references/issue-references.md`:

- Closing keywords (`Closes/Fixes/Resolves #N`) — verify the diff actually resolves the linked work (`gh issue view N`). If not → flag as overreaching (suggest downgrade to context-ref).
- Context-refs (`Refs/See/Related/bare #N`) — verify the diff still relates. If not → flag for removal.

### 4. Map claims to changes

Build a two-way mapping. Mark each entry:

| State | Meaning |
|---|---|
| `covered` | Claim is supported by changes; change is mentioned by a claim |
| `stale` | Claim describes work no longer in the diff (reverted, refactored away) |
| `missing` | Change is meaningful and undocumented in the description |
| `partial` | Claim's magnitude or direction is wrong (e.g., "updates 2 files" but 5 changed) |
| `inverted` | Claim contradicts the change (e.g., "adds X" but X was removed) |

**Trivial** (no claim needed): formatting / whitespace, generated lockfile updates with no manual edit, import reordering, comment-only changes, mechanical single-line version bumps.

**Not trivial:** any logic change, config-value change, new/deleted file, dep-version change with non-mechanical impact, security-relevant config, public-API surface change.

**Cap output:** omit `covered` rows unless they directly justify the verdict.

### 5. Classify the verdict

- **IN-SYNC** — all claims `covered`, no findings above trivial threshold.
- **MINOR-UPDATE** — small fraction (≤~20%) `missing` or one `partial`; no escalator. Output: **section-level patch**.
- **MAJOR-REWRITE** — any `inverted`, or `missing` / `stale` changing headline meaning, or any escalator below fires. Output: **full proposed body**.
- **HANDOFF-TO-WRITE** — body is empty / WIP / one-liner / unfilled-template. Output: stop and direct the user to invoke `pr-description-write` (this capability does not author from scratch).
- **EMPTY-DIFF** — `changedFiles == 0`. Stop; suggest closing PR or explaining.

**Domain escalators** — any of these force MAJOR-REWRITE regardless of finding count:

- Schema / data migration (`migrations/**`, `*.sql`, schema files)
- Security-relevant (auth, permissions, crypto, secrets handling, CORS, CSP)
- Public-API (exported symbols, route changes, breaking signatures, response shape)
- Dependency / runtime non-mechanical (major version bump, new transitive deps)
- CI / release-workflow (`.github/workflows/**`, release scripts, deploy configs)
- User-visible behavior (UI text, default config, exit codes, output format)

Borderline MINOR vs MAJOR → prefer MAJOR. Rewrite is cheaper than misleading a reviewer.

**Title staleness check:** compare title against diff intent. Stale conventional-commit prefix (`feat(api):` on a PR that no longer touches `api/`), leftover `[WIP]` / `[DRAFT]`, mismatched scope → flag as "title-stale". **Do not auto-edit** the title; surface for the user.

### 6. Produce output

Report in this order:

1. **Verdict** — one of the five labels, one sentence justifying it. Note sampling or missing-data caveats.
2. **Findings** — table sorted `inverted` → `stale` → `missing` → `partial` (omit `covered` unless explanatory).
3. **Title note** — only if title-stale.
4. **Proposed description** (MINOR / MAJOR only) — full markdown or section-level patch per Step 5. Show **inline** AND write to a `mktemp` file. Preserve every trailer per `../../references/trailer-semantics.md`.
5. **Apply command** — `gh pr edit <num> --body-file <path>` with the **resolved PR number explicitly**, never a branch name. Never run automatically.

**Pre-display secret scan** per `../../references/secret-patterns.md`. On match → redact + WARN. Never include detected secrets.

**Body length cap** — GitHub limit is 65,536 chars. Warn if proposal >~65,000.

**For MAJOR-REWRITE on borderline-empty descriptions** — pulling motivation context from `gh pr view <num> --comments` and `gh api .../pulls/<num>/reviews` is allowed sparingly. For truly empty bodies, hand off to `pr-description-write` instead.

### 7. Squash-with-`PR_BODY` shape

When `sm == "PR_BODY"`, MAJOR-REWRITE proposals must be commit-message-shaped: imperative subject ≤72 chars, flat body, no markdown headings. Template in `../../references/merge-policy.md`.

## Edge cases

- **Draft PR** — looser polish bar, NOT looser accuracy bar. Inverted / stale claims still misclassify reviewers' time.
- **Stacked PRs, force-pushed branch, fork PRs, `origin` not upstream, fetch failure** — see `../../references/git-gh-quirks.md`.
- **Squash-merge / rebase-merge target** — see `../../references/merge-policy.md`.
- **Repo-specific conventions** — `CLAUDE.md`, `AGENTS.md`, `.github/copilot-instructions.md`, `CONTRIBUTING.md`, PR template, commitlint config. Precedence and per-file rules in `../../references/format-conventions.md`.
- **Trailers** — semantics depend on merge mode and trailer type. Detailed rules in `../../references/trailer-semantics.md`.
- **Large PRs (>50 files)** — deterministic sampling per Step 2; note "sampled" in verdict.

## Anti-patterns

- Don't rewrite a description just because it could be "better" — only when wrong, stale, or incomplete against the diff.
- Don't invent test-plan items. If the existing plan is wrong, mark `stale` and replace with `Verification pending — to be confirmed by author`.
- Don't strip context the user added (motivation, design links, screenshots) — carry forward unless now wrong.
- Don't publish secrets from diffs into the proposed body — run the Step 6 secret scan.
- Don't run `gh pr edit` without confirmation, even on "fix it" — show the proposal first.
- Don't classify on file count alone — one inverted claim or one escalator outweighs ten covered ones.
- Don't auto-edit the PR title even on title-stale — flag and let the user decide.
- Don't author a body from scratch — hand off to `pr-description-write` when the body is empty / WIP / unfilled.

## Verdict decision table

| Findings present | Escalator fires? | Verdict |
|---|---|---|
| `changedFiles == 0` | — | `EMPTY-DIFF` |
| Body empty / WIP / one-liner / unfilled template | — | `HANDOFF-TO-WRITE` |
| Only `covered` (trivial gaps OK) | No | `IN-SYNC` |
| Small fraction (≤~20%) `missing` or 1 `partial`, no `inverted` / `stale` | No | `MINOR-UPDATE` |
| Any `inverted`, or higher-fraction `missing` / `stale` | — | `MAJOR-REWRITE` |
| Any findings at all touching schema / security / public API / deps / CI / user-visible behavior | Yes | `MAJOR-REWRITE` |
