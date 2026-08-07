# Forge portability

Load this when the skill is run against a repo whose forge is not GitHub. The house style and most checks assume GitHub (`gh`, Actions, rulesets, Dependabot, the community-profile API), but the _concepts_ — CI, protected branches, dependency bots, releases, vulnerability reporting — exist on every modern forge under different names. This reference says what's GitHub-specific, how it maps, and how to **degrade rather than fabricate** on GitLab, Codeberg/Forgejo, and Bitbucket Cloud.

## Detecting the forge

Run once, cache for the session:

```bash
git remote get-url origin
```

| Hostname pattern | Forge | CLI |
| --- | --- | --- |
| `github.com`, `ghe.*` | GitHub | `gh` |
| `gitlab.com`, self-hosted GitLab | GitLab | `glab` |
| `codeberg.org`, any Forgejo instance | Codeberg / Forgejo | `tea` (the Gitea CLI; Forgejo is wire-compatible) |
| `bitbucket.org` | Bitbucket Cloud | `curl` + scoped API token |

For ambiguous self-hosted hosts, probe `…/api/v4/version` (GitLab) or `…/api/v1/version` (Gitea/Forgejo). No match → report "forge unknown; GitHub-specific checks marked `unknown`" and audit on-disk files only.

## What's GitHub-specific in this skill, and how it maps

| Skill concept (capability) | GitHub | GitLab | Codeberg / Forgejo | Bitbucket Cloud |
| --- | --- | --- | --- | --- |
| CI workflows (ci-automation, automation-baseline) | Actions `.github/workflows/` | `.gitlab-ci.yml` | Actions (Forgejo) / Woodpecker | Pipelines `bitbucket-pipelines.yml` |
| Branch/tag protection (branch-protection.md) | rulesets / branch protection | protected branches + push rules | branch protection | branch restrictions |
| Required-checks gate (pr-autonomy) | required status checks | MR pipeline-must-succeed | status checks | merge checks |
| Auto-merge (pr-autonomy, dependency-supply-chain) | `gh pr merge --auto` | MR auto-merge (`glab mr merge --auto-merge`) | API-only (`merge_when_checks_succeed`; not exposed by `tea`) | "merge when builds pass" — a branch-restriction merge check; per-PR arming is UI-only |
| Dependency updates (dependency-supply-chain) | Dependabot | Renovate / GitLab Dependency Scanning | Renovate | Renovate |
| Code scanning (security-policy, automation-baseline) | CodeQL | GitLab SAST | external SAST | external SAST |
| Releases (release-versioning) | Releases + `gh release` | Releases + `glab release` | Releases + `tea release` | no native Releases (tags + downloads) |
| Health % (oss-health-rubric.md) | community-profile API | none — score the files directly | none | none |
| Automation identity (automation-identity.md) | GitHub App / fine-grained PAT | project/group access token, CI job token | app/access token | scoped API token (app passwords no longer work) / OAuth |
| Secret stores (automation-prerequisites.md) | Actions + Dependabot stores | CI/CD variables (no split) | secrets | repository variables |

## Degrade rules

- **File-based checks are forge-agnostic** — `LICENSE`, `README`, `CONTRIBUTING`, `CODE_OF_CONDUCT`, `CHANGELOG`, `.editorconfig`, lockfiles, SPDX headers all audit identically on any forge (or none). Run them everywhere.
- **Settings-based checks** (branch protection, auto-merge, alerts, community-profile %) are read via `gh`/the GitHub API. On another forge, either read the equivalent (`glab`/`tea`/`curl`) when wired, or mark the check `unknown` — never assume absent and never fabricate a GitHub-shaped result.
- **Dependabot is GitHub-only.** On GitLab/Forgejo/Bitbucket, propose **Renovate** instead (dependency-supply-chain already offers it) — don't write a `.github/dependabot.yaml` that the forge will ignore.
- **The autonomous-update recipe and the prerequisites runbook are GitHub-shaped** (`gh`, the Actions/Dependabot secret-store split, App tokens). On other forges, keep the _shape_ — identity, required-checks gate, gating labels, reconcile — but translate to that forge's CI and token model; the dual-store split is GitHub-specific and drops away.

## What the skill does not promise

- **Feature parity.** Bitbucket has no native Releases; GitLab/Forgejo health has no community-profile equivalent (score the files directly instead).
- **Authentication.** How `glab` / `tea` / `curl` are authenticated is harness configuration; assume the CLI is logged in and surface a clear error if not.
- **Self-hosted deltas.** GitHub Enterprise, GitLab self-managed, Forgejo, and Bitbucket Data Center have schema deltas from their hosted siblings — treat the host probe as a hint, and degrade on API errors.

House default remains GitHub (the maintainer's fleet); this file is the graceful-degrade path, not a second first-class target.
