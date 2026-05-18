# Forge adapters

Load this when a GitHub-side capability is invoked against a repo whose forge is not GitHub. The skill's capabilities reference `gh` directly today, but the *concepts* — pull requests, reviews, merge policies, releases — exist on every modern forge under different names and CLI surfaces.

This reference maps each GitHub concept to its equivalent on GitLab, Codeberg (Forgejo), and Bitbucket Cloud so a capability can degrade gracefully or route through an alternative CLI when `gh` is unavailable or the remote is not GitHub.

## Detecting the forge

Run once, cache for the session:

```
git remote get-url origin
```

Pattern match on the host:

| Hostname pattern | Forge | CLI |
|---|---|---|
| `github.com`, `*.github.com`, `ghe.*` | GitHub | `gh` |
| `gitlab.com`, self-hosted GitLab (any host with `/api/v4/`) | GitLab | `glab` |
| `codeberg.org`, any Forgejo instance | Codeberg / Forgejo | `tea` (Gitea CLI; Forgejo is wire-compatible) |
| `bitbucket.org` | Bitbucket Cloud | no official CLI; HTTP API via `curl` |

For ambiguous self-hosted instances, fall back to a `curl -s <url>/api/v4/version` probe (GitLab) or `<url>/api/v1/version` (Gitea/Forgejo). If no probe matches, the capability surfaces "forge unknown; GitHub-side operations unavailable" and offers the git-side equivalent where one exists.

## Concept mapping

| GitHub concept | GitLab | Codeberg / Forgejo | Bitbucket Cloud |
|---|---|---|---|
| Pull Request | Merge Request (MR) | Pull Request | Pull Request |
| `gh pr view <n>` | `glab mr view <n>` | `tea pr view <n>` | `curl -s .../pullrequests/<n>` |
| `gh pr create` | `glab mr create` | `tea pr create` | `curl -X POST .../pullrequests` |
| `gh pr edit --body` | `glab mr update --description` | `tea pr edit --description` | `curl -X PUT .../pullrequests/<n>` |
| `gh pr merge` | `glab mr merge` | `tea pr merge` | `curl -X POST .../pullrequests/<n>/merge` |
| `gh pr checks` | `glab ci status` | `tea pr status` (limited) | `curl -s .../statuses/<sha>` |
| `gh pr review` | `glab mr approve` / `glab mr note` | `tea pr review` | `curl -X POST .../pullrequests/<n>/approve` |
| Merge policies (squash / merge / rebase) | "Merge method" project setting; `merge_method` in API | "Merge style" repo setting | "Merge strategy" repo setting |
| `gh release create` | `glab release create` | `tea release create` | `curl -X POST .../downloads` (no native Releases concept) |
| `gh api <path>` | `glab api <path>` | `curl -s .../api/v1/<path>` | `curl -s api.bitbucket.org/2.0/<path>` |

## Capability adaptation

Each GitHub-side capability should treat `gh` invocations as one branch of a switch keyed on detected forge:

```
forge = detect_forge()
if forge == "github":
    use gh ...
elif forge == "gitlab" and shutil.which("glab"):
    use glab ...
elif forge == "forgejo" and shutil.which("tea"):
    use tea ...
elif forge == "bitbucket":
    use curl ... with stored credentials
else:
    surface: "<forge> support not wired in this capability; falling back to git-side equivalent"
    offer the local-only proposal if one exists, or stop with a clean message
```

Capabilities that have no git-side equivalent (e.g., `pr-checks-summary`, `merge-execute`, `merge-readiness`, `release-notes`) should refuse cleanly rather than producing a degraded GitHub-shaped output on a non-GitHub forge.

## What the skill does NOT promise

- **Feature parity.** Bitbucket has no native Releases concept; emulating it via downloads is out of scope. Forgejo's review-thread API differs subtly from GitHub's; thread state may not round-trip exactly.
- **Authentication.** This file does not specify how each CLI is authenticated; that is harness configuration. The capability assumes the CLI is logged in and surfaces a clear error if not.
- **Self-hosted variants.** Self-hosted GitHub Enterprise, GitLab self-managed, Forgejo, and Bitbucket Server (a.k.a. Bitbucket Data Center) all have schema deltas from their hosted siblings. Capabilities should treat the hostname probe as a hint, not a guarantee, and degrade on API errors.

## Migration plan for existing GitHub-side capabilities

This reference is descriptive today. Capabilities still hardcode `gh`. The migration is staged:

1. **Phase 1 (now).** Add `detect_forge()` to each GitHub-side capability's input-guard step; surface "forge=<x>; capability uses gh by default" in the proposal preamble so the user sees the assumption.
2. **Phase 2.** Wrap `gh` invocations with the switch above for capabilities where the alternative CLIs (`glab`, `tea`) have direct equivalents (`pr view`, `pr create`, `pr edit`, `pr merge`).
3. **Phase 3.** Plumb `curl + token` paths for Bitbucket Cloud where the operation justifies the work (PR view + edit + merge are most common).

Skip phases 2 and 3 for capabilities whose GitHub-side logic is too intricate to port (`pr-checks-summary` parses GitHub Actions logs that have no equivalent shape on other forges).
