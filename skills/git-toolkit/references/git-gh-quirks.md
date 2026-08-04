# Git / gh quirks: fork PRs, force-pushes, stacked PRs, fetch degrade, Windows shells

Load this when a capability needs to branch on repo topology, recover from a non-trivial git/gh failure mode, or run its commands on a Windows shell.

## Repo-topology branching

Decide which path to use from the PR metadata fetch:

- **Cross-repo / fork PR** when `isCrossRepository == true`, OR `baseRepository.url` doesn't match the local `origin` remote URL.
- **Same-repo PR** otherwise.

### Cross-repo / fork path

Local git has neither the head commits nor the right base — use remote-authoritative reads only:

```
gh api repos/{owner}/{repo}/pulls/{num}/files --paginate --jq '.[].filename'
gh pr diff <num> --patch
gh pr view <num> --json commits --jq '.commits[] | "\(.oid[0:7]) \(.messageHeadline)"'
```

Skip every `git` invocation. Pagination matters for large PRs — GitHub's `pulls/.../files` returns 30 per page by default and the second page is silently dropped without `--paginate`.

### Same-repo path

Run in parallel:

```
git fetch origin <baseRefName>
git log --no-merges origin/<baseRefName>..HEAD --pretty=format:'%h %s'
git diff --stat origin/<baseRefName>...HEAD
```

`--no-merges` strips "merge main into feature" noise from the commit subject list.

## Two-dot vs three-dot — intentional asymmetry

- `git log A..B` (two-dot) = commits reachable from B but NOT A. The right set for "commits unique to this branch since it diverged."
- `git diff A...B` (three-dot) = diff from `merge-base(A, B)` to B. Stable when A advances during the PR's lifetime, so the footprint doesn't drift when the base gets new commits.

Do not "harmonize" them. Two-dot diff would include base-branch commits that landed after the PR was opened (wrong file set); three-dot log would not exist in the form needed (it has different semantics).

## Force-push / out-of-sync local head reconciliation

Compare local `git rev-parse HEAD` to `headRefOid` from the metadata fetch. They diverge when:

- Another machine force-pushed
- CI pushed a commit (lint fix, format, autorelease)
- The local checkout is stale (`git pull` not run)

On divergence: discard the same-repo local-git results and re-run the cross-repo path against `gh pr diff <num>`. Do not silently use the local diff — it represents a different code state than what reviewers see on the PR.

## `git fetch` graceful degrade

`git fetch origin <baseRefName>` can fail for:

- Offline
- gh / git auth expired
- Base lives on a fork that `origin` doesn't track
- Network restrictions in CI

Don't hard-stop. Warn, proceed with the existing `origin/<base>` ref (whatever was last fetched), and flag in the verdict: `WARN: base ref not refreshed — N commits possibly missing from comparison`. The user can decide whether to re-run with connectivity.

## Stacked-PR base resolution

When the PR's base is itself another feature branch (stacked PR pattern):

- The diff target is `baseRefName` from `gh pr view`, NOT `main`.
- The base may live on the contributor's fork or on a non-`origin` remote. Resolve `baseRepository.url`; fetch from there with `git fetch <url> <baseRefName>` if it isn't already in your local refs.
- If the base is a local-only branch (no remote at all), skip the fetch and warn — the diff is still computable from whatever local copy of the base exists, but it might be out of sync with the parent PR.

Stacked PRs cause two common failure modes when ignored:

- Diffing against `main` includes the parent PR's changes → reports them as missing from the description.
- Diffing against an unfetched stacked base computes against stale commits → misses recent changes from the parent PR.

## `origin` is not always the upstream remote

For fork checkouts, `origin` points to the fork — `git fetch origin main` fetches the fork's `main`, not the upstream. Always resolve the true base/head remotes from `baseRepository.url` and `headRepository.url`. Never hardcode `origin` in commands when the cross-repo branch applies. For same-repo PRs, the `origin == upstream` assumption holds.

## Review-thread resolution state (GraphQL `reviewThreads`)

REST (`pulls/{n}/comments`) doesn't expose thread resolution state — reading `isResolved` requires GraphQL. The canonical query:

```
gh api graphql -f query='
query($owner: String!, $repo: String!, $pr: Int!, $endCursor: String) {
  repository(owner: $owner, name: $repo) {
    pullRequest(number: $pr) {
      reviewThreads(first: 100, after: $endCursor) {
        pageInfo { hasNextPage endCursor }
        nodes {
          id
          isResolved
          isOutdated
          path
          line
          comments(first: 20) {
            nodes {
              databaseId
              author { login }
              body
              createdAt
              commit { oid }
            }
          }
        }
      }
    }
  }
}' -F owner=<o> -F repo=<r> -F pr=<num>
```

`reviewThreads` is capped at 100 per page. For PRs with more threads, loop on the cursor: pass `-F endCursor=<endCursor>` from the previous page while `pageInfo.hasNextPage` is true, accumulating `nodes` across pages — otherwise threads past the first 100 are silently dropped, undercounting any unresolved-thread total built from them. (`gh api graphql --paginate` automates this only when the query declares a variable literally named `$endCursor` and exposes `pageInfo { hasNextPage endCursor }`, as above — `gh` ignores any other cursor variable name.)

## `gh` not authenticated

`gh pr view` (and any other `gh` call) exits non-zero with an auth-related error message. Detect this case, tell the user to run `gh auth login`, and stop. Do not parse the error message beyond detecting it's auth-related — `gh`'s error format is not a stable contract. Do not fall back to anonymous API calls — they hit the unauthenticated rate limit (60/hour) and the capability needs more headroom.

## Reading commits without `gh`

For commit-message work that doesn't need PR context, `git` alone is enough:

```
git show <sha> --no-patch --format='%H%n%s%n%n%b'
git log <range> --pretty=format:'%H%x09%s'
git rev-parse HEAD
```

Use these when working pre-PR or on local-only branches; reserve `gh` calls for PR-aware operations.

## Shell portability (Windows)

Every command in this skill is written for a POSIX shell. On Windows the zero-translation path is **Git Bash**, bundled with every standard Git for Windows install (winget `Git.Git`): heredocs, `mktemp`, and `$(cat …)` run as written. PowerShell works with the alternates below. cmd.exe is not supported — propose Git Bash or PowerShell instead.

The apply commands are file-based by design (`git commit -F <path>`, `--body-file <path>`, `--notes-file <path>`), and those flags are shell-agnostic — only creating and filling the proposal file needs translation:

| POSIX pattern | PowerShell equivalent |
|---|---|
| `mktemp` | `New-TemporaryFile` (PowerShell ≥ 5.0; returns a FileInfo — use `.FullName`) |
| writing the proposal file | `[System.IO.File]::WriteAllText($path, $text)` — BOM-less UTF-8 on every PowerShell version. `Set-Content -Encoding utf8` also works but adds a BOM on Windows PowerShell 5.1, and bare `>` is never safe there — 5.1 redirection writes UTF-16LE, which file-consuming flags choke on |
| heredoc (`<<'EOF'`) | single-quoted here-string (`@'` … `'@`) — the closing mark must start its own line; the double-quoted form interpolates |
| `$(cat <path>)` | `(Get-Content <path> -Raw)` — `-Raw` returns one string; without it `Get-Content` (and its `cat` alias) returns an array of lines |
| `--pretty=format:'%h %s'` and similar mid-token quoting | quote the whole argument instead: `'--pretty=format:%h %s'` — robust across PowerShell versions and argument-mode metacharacters |
| `curl` (the Bitbucket lane's fallback) | call `curl.exe` explicitly — Windows PowerShell 5.1 aliases `curl` to `Invoke-WebRequest`; PowerShell 7 resolves the real binary, but the `.exe` form is unambiguous everywhere |

### Windows install channels

All four forge CLIs ship Windows builds. winget carries `gh` officially; the glab, tea, and bkt packages are community-maintained:

| CLI | winget id | scoop | choco |
|---|---|---|---|
| `gh` | `GitHub.cli` | `gh` | `gh` |
| `glab` | `GLab.GLab` | `glab` | `glab` |
| `tea` | `Gitea.tea` | `tea` | `tea` — the `gitea` package is the server, not the CLI |
| `bkt` | `AvivSinai.Bitbucket-CLI` | `bitbucket-cli` — via the project's own bucket (`scoop bucket add avivsinai`) | not packaged — use the release zips |

Official binaries as the fallback: gh's releases (MSI/exe), gitlab-org/cli releases, dl.gitea.com/tea for `tea`, and avivsinai/bitbucket-cli releases (windows zip) for `bkt`.
