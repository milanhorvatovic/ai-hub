# Forge adapters

The single home of the forge mapping for forge-side capabilities. Capability bodies express each operation once, with the GitHub (`gh`) command as the worked example; the tables here map those operations onto GitLab (`glab`) and Codeberg/Forgejo (`tea`), plus a minimal `curl` lane for Bitbucket Cloud, so the lane switch in `pr-input-guards.md` can route a capability end-to-end on a non-GitHub remote. The mapping lives only here — a structural test in the shipping repo rejects `glab`/`tea`/Bitbucket-API literals in capability bodies — so a CLI rename or flag change is a one-file fix.

Per-capability promises (what routes fully, what degrades to a labeled partial, what refuses) live in the router's tier table and each capability's guard section; this file supplies the commands those promises route to.

## Detecting the forge

Run once, cache for the session:

```
git remote get-url origin
```

Pattern match on the host:

| Hostname pattern | Forge | Lane |
|---|---|---|
| `github.com`, `*.github.com`, `ghe.*` | GitHub | `gh` |
| `gitlab.com`, self-hosted GitLab (any host with `/api/v4/`) | GitLab | `glab` |
| `codeberg.org`, any Forgejo instance | Codeberg / Forgejo | `tea` (the Gitea CLI; Forgejo is wire-compatible — divergences flagged below) |
| `bitbucket.org` | Bitbucket Cloud | `bkt` (community CLI) with a tool-free curl fallback — minimal lane, see its section below |

For ambiguous self-hosted instances, fall back to a `curl -s <url>/api/v4/version` probe (GitLab) or `<url>/api/v1/version` (Gitea/Forgejo). If no probe matches, the capability surfaces "forge unknown; forge-side operations unavailable" and offers the git-side equivalent where one exists.

## Command lanes

- **`gh`** — first-class; capability bodies are written in it.
- **`glab`** (GitLab CLI) — authenticate with `glab auth login`. `glab mr view` / `glab issue view` / `glab ci status` take `-F json` and a built-in `--jq`; `glab api` substitutes `:id`, `:branch`, `:username`, `:fullpath` from the current repo and supports `--paginate` but has **no** built-in `--jq` — pipe to `jq` and name that dependency in the proposal.
- **`tea`** (Gitea CLI) — authenticate with `tea login add --url <instance> --token <token>`. Works against Forgejo/Codeberg; list commands double as detail views (`tea pr <n>`, `tea issues <n>`) and machine-readable output comes from `--fields` selections rather than JSON.
- **`bkt`** (Bitbucket Cloud — the community CLI at avivsinai/bitbucket-cli; gh-inspired, MIT, also speaks Bitbucket Data Center; Atlassian's own `acli` ships no Bitbucket command group, and projects named "acli"/"atlassian-cli" that advertise one are different tools) — authenticate with `bkt auth login https://bitbucket.org --kind cloud --username <atlassian-email> --token <api-token>`, using a **scoped API token** created at id.atlassian.com with Bitbucket as the application (general Atlassian tokens won't work; app passwords are dead; OAuth via `--web` is the alternative). Scopes: `read:pullrequest:bitbucket` for PR reads, `write:pullrequest:bitbucket` for edit/merge, `read:repository:bitbucket` for commit statuses. Every command takes `--json` and a built-in `--jq`; `bkt api <path>` is the passthrough for reads without a dedicated command. The project is young (pre-1.0, one primary maintainer) — pin its version in automation, and on command-surface drift trust `--help` and fix this table. The raw REST calls in the lane table are the tool-free fallback: same token, `curl` + `jq`.

A missing or unauthenticated lane CLI stops the capability (per the guard sequence) — name the CLI and its auth command, and never emit another lane's commands as a substitute. The one exception is Bitbucket: with `bkt` absent, the lane's curl fallback still routes.

## Concept vocabulary

| GitHub | GitLab | Codeberg / Forgejo | Bitbucket Cloud |
|---|---|---|---|
| Pull Request (PR) | Merge Request (MR) | Pull Request | Pull Request |
| Draft PR | Draft MR (`Draft:` title prefix, `draft` field) | `WIP:` title prefix (API `draft` field) | Draft PR |
| Review thread | Discussion | Review conversation | Comment thread |
| Checks (`statusCheckRollup`) | Pipelines / jobs | Commit statuses | Pipelines |
| Merge method (per-merge choice) | `merge_method` project setting + per-MR squash flag | Merge style (per-merge choice) | Merge strategy (per-merge choice) |
| Releases | Releases | Releases | none (tags + downloads) |

## Operation mapping

`<n>` is the PR number / MR iid / PR index. Rows marked *(optional)* are enrichment reads — skip them with a note when the lane has no cheap equivalent.

### Resolve and read

| Operation | GitHub (worked example) | GitLab (`glab`) | Codeberg / Forgejo (`tea`) |
|---|---|---|---|
| PR for the current branch | `gh pr list --head <branch> --state all` | `glab mr list --source-branch <branch> -F json` | `tea pr list -f index,head,state` and match the head branch |
| PR metadata | `gh pr view <n> --json <fields>` | `glab mr view <n> -F json` | `tea pr <n>` (detail view — there is no `view` subcommand); field selections via `tea pr list -f <fields>` |
| Field-level reads | `gh api repos/{o}/{r}/pulls/<n>` | `glab api projects/:id/merge_requests/<n>` piped to `jq` — `draft`, `has_conflicts`, `blocking_discussions_resolved`, `head_pipeline`, `detailed_merge_status` (`merge_status` is deprecated) | `tea pr list` fields include `mergeable`, `base`, `head`, `ci`; no `draft` field — check the `WIP:` title prefix |
| PR diff | `gh pr diff <n> --patch` | `glab mr diff <n>` | `patch` / `diff` fields of `tea pr list -f`, or `tea pr checkout <n>` + local `git diff` |
| Commits on the PR | `gh pr view <n> --json commits` | `glab api projects/:id/merge_requests/<n>/commits` piped to `jq` | `tea pr checkout <n>` + local `git log` |
| Issue detail | `gh issue view <N> --json <fields>` | `glab issue view <N> -F json` | `tea issues <N>` (same list/detail pattern) |
| Merge policy | `gh api repos/{o}/{r} --jq '{squash: .allow_squash_merge, …}'` | `glab api projects/:id` piped to `jq '{merge_method, squash_option, squash_commit_template}'` — semantics below | the style is chosen at merge time; squash-message shaping is an on-disk template read (below) |
| Branch protection *(optional)* | `gh api repos/{o}/{r}/branches/<base>/protection` (needs permissions) | `glab api projects/:id/protected_branches` piped to `jq` (readable with code-read access) | API read requires a repo-admin token — without one, report the gate as not readable |
| PR comments for context *(optional)* | `gh pr view <n> --comments` | `glab api projects/:id/merge_requests/<n>/notes` piped to `jq` | skip |
| Author's merged-PR count *(optional)* | `gh pr list --author <login> --state merged` | `glab api "projects/:id/merge_requests?state=merged&author_username=<login>"` piped to `jq length` | skip |
| Issue↔PR cross-references *(optional)* | `gh api repos/{o}/{r}/issues/<N>/timeline` | `glab api projects/:id/issues/<N>/related_merge_requests` piped to `jq` | skip |

### Edit and apply

| Operation | GitHub (worked example) | GitLab (`glab`) | Codeberg / Forgejo (`tea`) |
|---|---|---|---|
| Edit the PR body | `gh pr edit <n> --body-file <path>` | `glab mr update <n> --description "$(cat <path>)"` — no file flag | `tea pr edit <n> --description "$(cat <path>)"` |
| Mark ready | `gh pr ready <n>` | `glab mr update <n> --ready` | edit the `WIP:` title prefix away via `tea pr edit <n> --title` |

### Review threads

| Operation | GitHub (worked example) | GitLab (`glab`) | Codeberg / Forgejo (`tea`) |
|---|---|---|---|
| List threads + resolution state | GraphQL `reviewThreads` query (see `git-gh-quirks.md`) | `glab api projects/:id/merge_requests/<n>/discussions --paginate` piped to `jq` — notes carry `resolvable` / `resolved` | `tea pr review-comments <n>` — the `resolver` field marks resolved comments (empty = unresolved) |
| Reply to a thread | GraphQL `addPullRequestReviewThreadReply` | `glab api -X POST projects/:id/merge_requests/<n>/discussions/<discussion-id>/notes -f body='<text>'` (thread-scoped; a bare `glab mr note create` posts a new top-level comment instead) | `tea pr reply <n> <comment-id> '<text>'` |
| Resolve a thread | GraphQL `resolveReviewThread` | `glab mr note resolve <n> <discussion-id>` | not exposed on Forgejo — resolving stays in the UI (Gitea ≥ 1.26 adds `tea pr resolve`) |
| Approve / request changes | `gh pr review --approve` / `--request-changes` | `glab mr approve <n>` / `glab mr note create <n> -m '<text>'` | `tea pr approve <n>` / `tea pr reject <n>` |
| Aggregate approval state | `reviewDecision` from `gh pr view` | `glab api projects/:id/merge_requests/<n>/approvals` piped to `jq '{approved, approvals_left}'` | unmapped — report the gate as not readable |

### Merge

| Operation | GitHub (worked example) | GitLab (`glab`) | Codeberg / Forgejo (`tea`) |
|---|---|---|---|
| Merge | `gh pr merge <n> --squash --delete-branch` | `glab mr merge <n> --squash --remove-source-branch` | `tea pr merge <n> --style squash` (styles: `merge`, `rebase`, `squash`, `rebase-merge`) |
| Merge when CI passes | `--auto` | `--auto-merge` — **defaults on**: pass `--auto-merge=false` to force an immediate merge while a pipeline runs | not exposed by tea — surface as unavailable |
| Delete the source branch | `--delete-branch` | `--remove-source-branch` | no flag — propose `git push <remote> --delete <branch>` after the merge |

### Checks / CI

| Operation | GitHub (worked example) | GitLab (`glab`) | Codeberg / Forgejo (`tea`) |
|---|---|---|---|
| CI status for the PR head | `gh pr view <n> --json statusCheckRollup` | `glab ci status -b <source-branch> -F json` (defaults to the current branch), or `head_pipeline` from the single-MR read | `ci` field of `tea pr list -f index,ci`; detail via API `GET /repos/{o}/{r}/commits/{ref}/status` |
| Pipeline / job detail | `gh run view <run-id>` | `glab ci view` | none |
| Failed-job logs | `gh run view <run-id> --log-failed` | `glab ci trace <job-id>` — raw log only; the failure-classification pass parses GitHub Actions log shape and stays GitHub-only, which is why the checks capability degrades to a labeled status-only partial on GitLab | none |

### Releases

| Operation | GitHub (worked example) | GitLab (`glab`) | Codeberg / Forgejo (`tea`) |
|---|---|---|---|
| Create a release with notes | `gh release create <tag> --notes-file <path>` | `glab release create <tag> --notes-file <path>` | `tea releases create --tag <tag> --title <title> --note-file <path>` |

The release-notes capability emits only the detected forge's line; on Bitbucket it surfaces the paste-in note instead (no native Releases).

## Merge and squash-message semantics off GitHub

GitHub picks the merge method per merge; GitLab splits the decision. `merge_method` (`merge`, `rebase_merge`, `ff`) is a project setting, and squash is a per-MR choice governed by `squash_option` (`never`, `always`, `default_on`, `default_off`). A capability proposing a merge on GitLab therefore reads the project settings and proposes flags consistent with them instead of offering a method menu — the server rejects a squash on a `never` project rather than negotiating.

The GitHub `sm == "PR_BODY"` rule (the PR body becomes the squash commit message, so drafts must be commit-message-shaped) has per-forge analogs:

- **GitLab** — the default squash commit message is `%{title}` alone, so the MR description is normally NOT the squash message. The analog fires only when the project's `squash_commit_template` contains `%{description}` — then shape the body exactly as for `PR_BODY` on GitHub.
- **Gitea / Forgejo** — the default squash message is `<PR title> (#<index>)` plus `Reviewed-on:` / `Reviewed-by:` trailers; the description enters it only when the repo ships `.gitea/default_merge_message/SQUASH_TEMPLATE.md` using `${PullRequestDescription}` — an on-disk read, no API needed. The merge command's title/message flags override the default in every case.
- **Bitbucket Cloud** — the strategy is a per-merge choice (six values, see the lane table). The default squash message is `Merged in <source branch> (pull request #<n>)` + the PR title + the consolidated commit-message list — the PR description is not reliably part of it, so never shape a body on the assumption it becomes the squash message; the merge call's `message` field is the explicit override. Bitbucket itself appends `Approved-by:` trailer lines to merge messages — forge-generated, not something a capability authors.

## Issue-closing keywords

GitLab supports the same closing keywords as GitHub (`Close`/`Fix`/`Resolve` families, case-insensitive) plus its own `Implement` family; the close fires when the MR merges to the project's **default branch**, and cross-project refs are `group/project#N`. Gitea/Forgejo default to the same `close`/`fix`/`resolve` families (server-configurable), actionable in commit messages and PR descriptions.

## Forgejo divergences

tea is the Gitea CLI; Forgejo (which powers Codeberg) stays wire-compatible with the Gitea API generation it forked from, not with current Gitea. The visible consequence here: the review-thread resolve endpoints exist only on Gitea ≥ 1.26, so on Forgejo `tea pr resolve` fails and resolution stays in the UI. Treat other `tea` errors on Forgejo the same way — degrade and say what didn't map, don't retry with guessed flags.

## Bitbucket Cloud lane (minimal)

The lane routes the highest-value operations through `bkt` (see Command lanes), with the raw REST calls as the tool-free fallback; capabilities whose operations are not in this table refuse on a Bitbucket remote, name that reason, and offer the git-side equivalent where one exists. release-notes is unaffected — it drafts on any forge and surfaces the paste-in note for publishing (Bitbucket has no native Releases and `bkt` has no tag or release commands; tags and Downloads only).

Fallback calls are `curl -s --user "$ATLASSIAN_EMAIL:$API_TOKEN"` against `https://api.bitbucket.org/2.0/repositories/<workspace>/<repo>` (shortened to `$BB`); `<workspace>/<repo>` comes from the detected remote URL (`bitbucket.org/<workspace>/<repo>.git`). List responses are paginated (default 10, max 100) — follow the `next` link in the body, or raise `pagelen`. `bkt` resolves the repo from the remote and paginates itself:

| Operation | `bkt` (primary) | curl fallback |
|---|---|---|
| PR for the current branch | no list filter by branch — use the passthrough: `bkt api "/repositories/{ws}/{repo}/pullrequests" -P 'q=source.branch.name="<branch>" AND state="OPEN"' --json` | `curl -sG … "$BB/pullrequests" --data-urlencode 'q=source.branch.name = "<branch>" AND state = "OPEN"'` |
| PR metadata | `bkt pr view <n> --json` — verify the JSON field shape on first use for `participants[].approved` | `GET $BB/pullrequests/<n>` — `state` (`OPEN` / `MERGED` / `DECLINED` / `SUPERSEDED`), `title`, `description`, `draft`, `participants[].approved`, `task_count` (open tasks), `close_source_branch`, `source.branch.name`, `destination.branch.name` |
| PR diff | `bkt pr diff <n>` (`--stat` for per-file counts) | `curl -sL … "$BB/pullrequests/<n>/diff"` — the endpoint redirects to the raw diff, so follow redirects (`-L`) |
| Edit the PR body | `bkt pr edit <n> --description '<text>'` — confirm reviewers survive the first edit you propose (whether bkt guards the underlying PUT's reviewers drop is unverified) | `GET` the PR first, then `PUT $BB/pullrequests/<n>` with `{"title": …, "description": …, "reviewers": <echoed from the GET>}` — a PUT that omits `reviewers` silently drops the PR's reviewer list |
| Merge policy | no dedicated command — `bkt api "/repositories/{ws}/{repo}/refs/branches/<name>" --jq '{merge_strategies, default_merge_strategy}'` | `destination.branch.merge_strategies` and `.default_merge_strategy` on the PR metadata read (also via `GET $BB/refs/branches/<name>`) — read-only, not settable via the API |
| Merge | `bkt pr merge <n> --strategy <strategy> --message '<override>'` — **bkt closes the source branch by default; pass `--close-source=false` to keep it** (the raw API defaults the other way) | `POST $BB/pullrequests/<n>/merge` with `{"merge_strategy": "<strategy>", "close_source_branch": <bool>, "message": "<override>"}` — strategies: `merge_commit` (API default), `squash`, `fast_forward`, `squash_fast_forward`, `rebase_fast_forward`, `rebase_merge`; drafts cannot merge (server-enforced) |
| Merge when CI passes | not on Cloud — `bkt pr auto-merge` is Data-Center-only; the scriptable near-equivalent is `bkt pr checks <n> --wait` then merge | UI-only — per-PR arming of "merge when builds pass" has no API path; the enablement toggle is a readable branch-restriction kind (`allow_auto_merge_when_builds_pass`), and the merge call's `async` param is job polling, not merge-when-green |
| CI status | `bkt pr checks <n>` (alias `builds`; `--wait` / `--timeout` for gating, exit code carries the verdict) | `GET $BB/pullrequests/<n>/statuses` (PR-level aggregate) or `GET $BB/commit/<sha>/statuses` — `state` ∈ `SUCCESSFUL` / `FAILED` / `INPROGRESS` / `STOPPED` |

Thread resolution and PR tasks are richer still (`bkt pr comments <n> --details`, threaded replies via `--parent`, `bkt pr comments resolve`, `bkt pr task list/create/complete`; API: `$BB/pullrequests/<n>/comments/<id>/resolve`, `$BB/pullrequests/<n>/tasks`), but no capability routes them — pr-conversation-resolve still refuses on Bitbucket, and merge-readiness reads only `task_count` from the metadata fetch.

## What the skill does NOT promise

- **Feature parity.** Thread resolution does not round-trip on Forgejo; GitLab's merge method is a project setting, not a per-merge choice; Bitbucket has no native Releases.
- **Authentication management.** The lane's CLI is assumed logged in (auth commands under Command lanes); on auth failure the capability stops per the guard sequence.
- **Self-hosted variants.** GitHub Enterprise, GitLab self-managed, Forgejo instances, and Bitbucket Server all have schema deltas from their hosted siblings. Treat the hostname probe as a hint, not a guarantee, and degrade on API errors.
- **CLI-version stability.** The tables reflect the CLIs' current documented surfaces. On a flag error, trust the CLI's `--help` over this table and fix the table — capability bodies never carry the mapping, so this file is the only place a CLI change lands.
