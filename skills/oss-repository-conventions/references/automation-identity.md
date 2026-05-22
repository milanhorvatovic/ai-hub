# Automation identity

Which identity an automation acts as — the most consequential choice for any CI / bot / autonomy flow. It governs least privilege, whether the action can **trigger downstream workflows**, whether it can **approve PRs**, how it rotates, how it's audited, and whether its commits show as **verified**.

## The options

| Identity | Scope | Triggers downstream workflows? | Can approve PRs? | Rotation | Audited as |
| --- | --- | --- | --- | --- | --- |
| **Default `GITHUB_TOKEN`** | the workflow's repo, per-job `permissions:` | No (anti-recursion) | No | auto, per-run | `github-actions[bot]` |
| **Fine-grained PAT** | selectable repos + scoped permissions | Yes | Yes | manual expiry | the user who created it |
| **Classic PAT** | broad (every repo the user can access) | Yes | Yes | manual | the user |
| **Custom GitHub App** | installed repos, fine-grained perms, short-lived (~1h) installation token | Yes | Yes | auto | the App's own identity |
| **Deploy key** | one repo, git read/write only | n/a (git, not API) | No | manual | the key |

## Choosing

- **Default `GITHUB_TOKEN` first** — least privilege, no secret to manage. Only reach past it for its two hard limits: it **can't approve PRs**, and its pushes/events **don't trigger** other workflows (a bot commit won't kick CI).
- **To trigger downstream workflows or approve PRs** (the autonomy ladder's L2+): a **GitHub App** installation token (preferred) or a tightly-scoped **fine-grained PAT**. Never a classic PAT.
- **For git-only push** (e.g. pushing built artifacts): a **deploy key** beats a PAT — no API surface.
- **Verified commits:** a GitHub App or the GitHub API (`createCommitOnBranch`) produces **verified** commits without managing signing keys; a PAT pushing over HTTPS does not (see `commit-signing.md`).

## Guardrails

- Store tokens/keys as repo/org **secrets**, never in files; mint App tokens **per-job** (`actions/create-github-app-token`) so they're short-lived.
- Grant the **minimum** permissions for the task — an over-scoped automation identity is the blast radius when a workflow or dependency is compromised.
- This file is the rationale behind the autonomy ladder's `autonomy-scoped-identity` guardrail (`pr-autonomy`): approval/merge running as the default token or an over-scoped PAT fails it.
