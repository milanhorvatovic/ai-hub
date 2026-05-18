---
name: commit-body-reflow
description: >
  Transforms the bodies of multiple existing commits (range, branch, set of
  branches) without changing tree content. Supports two transformations:
  flow (join hard-wrapped paragraphs into single lines) and wrap (hard-wrap
  flowing paragraphs at a column limit). Routes through the mass-rewrite
  procedure for stacked branches. Triggers on "reflow commit bodies",
  "convert these commits to flowing paragraphs", "hard-wrap the bodies at
  72", "fix wrap style across this branch".
---

# commit-body-reflow capability

Rewrites the bodies of many commits at once to switch between flowing-paragraph and hard-wrap styles, preserving subjects and trailers byte-for-byte. Use this when the entire branch (or set of branches) needs a consistent body style and per-commit `commit-amend-message` would be too tedious.

## Scope: git-side

This capability uses only `git` operations (`filter-branch`, `filter-repo`, `rebase --exec`). It does **not** depend on `gh` or PR concepts. The Force-Push Impact analysis (from `../../capabilities/commit-message/capability.md` Step 5) may use `gh` as optional enrichment to surface review anchors, but the core transformation runs on local git history without it.

## Mode detection

| User said | Mode |
|---|---|
| "flow these commit bodies" / "convert to flowing paragraphs" / "remove the hard-wrap" | **FLOW** |
| "hard-wrap at 72" / "wrap these bodies at 80" / "switch to hard-wrap" | **WRAP** (need: column limit) |
| "fix the wrap style across this branch" | Ask: which direction (flow or wrap), and what column if wrap. |

## Input guards

- Must be inside a git repo, working tree clean.
- Range must contain ≥2 commits; for a single commit, redirect to `commit-amend-message`.
- Identify all branches whose commits fall within the rewrite scope. Surface as a **Scope** block before any plan.
- **Bot guard** — per the router rule, skip bot-authored commits. The transformation script must detect `*[bot]@users.noreply.github.com` and emit the message unchanged.
- **Pushed-state check** — emit the Force-Push Impact block (commit-message Step 5) for each affected branch before showing the plan.

## Workflow

### 1. Resolve scope

```
git log --pretty=format:'%h %s' <base>..<branch>
git for-each-ref --format='%(refname:short) %(upstream:short)' refs/heads/
```

List target commits. Detect dependent branches via `git log --all --oneline` overlap or by querying `git branch --contains <commit>`. Emit:

```
Scope:
  Primary branch:        <branch>  (N commits)
  Dependent branches:    <list>    (rebase needed after rewrite)
  Shared ancestor depth: <K>       (commits shared with main)
```

### 2. Sample and confirm style

Read 3–5 representative commit bodies. Show the user the **first commit's** body as it is now, then as it would look after the transformation. Wait for confirmation.

For FLOW mode, the after-image is the same content with paragraphs joined per `../../references/format-conventions.md` flowing rules: paragraphs become single lines, blank lines preserved, lists keep one item per line.

For WRAP mode, the after-image is the same content rewrapped to the requested column limit, measured in display columns (not bytes) per `../../references/format-conventions.md`. Lists are not rewrapped.

### 3. Choose tool

Follow `../../references/mass-rewrite.md` tool-choice table:

- Prefer `git filter-repo --message-callback '<python>'` if installed.
- Fall back to `git filter-branch --msg-filter '<command>'` with `FILTER_BRANCH_SQUELCH_WARNING=1` set.
- Use `git rebase --exec '<script>'` only if the transformation needs commit-content access (FLOW and WRAP do not).

### 4. Pre-flight

```
git status --porcelain                     # must be empty
git tag pre-reflow/<branch> <branch>       # backup tag per affected branch
git log -1 --pretty=format:'%b' <sha> | <transform>  # idempotency check on one sample
```

If idempotency check shows a non-trivial diff on already-transformed content, halt and refine the script (FLOW with smart_join for kebab-case, WRAP with column-counting that skips multi-byte chars).

### 5. Per-branch sequencing

Per `../../references/mass-rewrite.md`:

1. Filter the topological-root branch first.
2. Rebase each dependent onto the new HEAD.
3. Filter the dependent's unique commits.
4. Repeat for next dependent level.

Each filter invocation passes a single `<base>..<branch>` range — never multiple refs at once (classifier-safe).

### 6. Post-flight verification

```
git log --oneline <base>..<branch>         # expected count, subjects unchanged
git log --pretty=format:'%b' <base>..<branch> | grep -E '<artifact-regex>'
git diff pre-reflow/<branch> <branch>      # MUST be empty (message-only changes don't show in diff)
```

The `git diff` against the backup tag should be empty for FLOW and WRAP — both transformations touch only messages, never trees. Any non-empty diff is a bug; halt and restore via `git reset --hard pre-reflow/<branch>`.

### 7. Surface verdict

Emit per `../../references/review-output.md`:

```
Transformation: <FLOW / WRAP@N>
Branches: <list>
Commits rewritten: <N>
Verdict: <COMPLETE / COMPLETE with K artifacts / FAILED>

If K > 0:
  Artifacts (review and decide whether to repair):
    <sha> <line>: <issue>
```

### 8. Publish

Per the Force-Push Impact block emitted in Step 1: if impact is `none`, no action. If `mild` or `high`, output the publish recipe; never auto-execute:

```
git push --force-with-lease origin <branch>
```

For multiple branches, one push per branch in dependent order (root first).

## Edge cases

- **Subject was already too long** (>72 chars). Reflow does not touch subjects. Subject violations are surfaced by `commit-message` REVIEW mode, not this capability.
- **Body contains a code fence or pre-formatted block** (e.g., a multi-line stack trace). FLOW must not join lines inside code fences (` ``` ` to ` ``` `) or inside indented (>= 4 spaces) blocks. Preserve verbatim.
- **Body contains trailers** (`Co-authored-by:`, `Signed-off-by:`, etc.). Trailers are preserved byte-for-byte, never reflowed. Detect via the trailer-block heuristic in `../../references/trailer-semantics.md`: contiguous lines at the end matching `^[A-Z][a-zA-Z-]+: `.
- **Body is empty.** No change; the transformation is a no-op for that commit.
- **Merge commits** in the range. Skip by default; merge-message format is tool-generated. The user can pass `--include-merges` to override.

## Anti-patterns

- Don't run filter-branch / filter-repo across multiple branches in a single invocation. Per-branch sequencing produces identical output without harness classifier risk (see `../../references/harness-safety-nets.md`).
- Don't combine a body reflow with any tree-content change in the same pass. Each is hard enough to verify alone.
- Don't reflow trailers. Ever.
- Don't add a `Co-Authored-By:` (or any other) trailer during reflow. The transformation preserves the existing message, nothing more (see router-level rule in `../../SKILL.md`).
- Don't auto-execute `git push --force-with-lease`. Surface the recipe; the user runs it.
- Don't run without pre-reflow tag backups. Recovery depends on them.
