# Bot signatures

Catalog of author patterns that identify commits / PRs as bot-authored. Capability bot-guards skip bot-authored work because the format is bot-controlled and any rewrite will be overwritten on the bot's next run. Load this when a capability needs to decide "is this author a bot?" rather than encoding patterns inline.

## How capabilities use this

Two checks are common:

- **Email-pattern check** (commit-message REVIEW mode, rebase-cleanup, commit-body-reflow): `git log -1 --pretty=format:'%ae' <sha>` returns the author email; match against the patterns below.
- **Login-pattern check** (GitHub-side capabilities with `gh pr view --json author`): `author.login` returns the username; match against the login patterns below.

A capability that matches either pattern should skip the commit / PR with a one-line note in the proposal preamble: `Skipping <sha-or-pr>: bot author <pattern> (see bot-signatures.md)`.

## GitHub-native bots

| Bot | Email pattern | Login pattern | Notes |
|---|---|---|---|
| Dependabot | `dependabot[bot]@users.noreply.github.com`, `49699333+dependabot[bot]@users.noreply.github.com` | `dependabot[bot]`, `dependabot-preview[bot]` (deprecated) | Numeric prefix is the account ID |
| Renovate | `bot@renovateapp.com`, `29139614+renovate[bot]@users.noreply.github.com` | `renovate[bot]`, `renovate-bot` | Self-hosted Renovate uses `renovate@<your-org>.com` patterns; allow override |
| GitHub Actions | `41898282+github-actions[bot]@users.noreply.github.com`, `github-actions[bot]@users.noreply.github.com` | `github-actions[bot]` | Used by `gh` CLI auto-commits and many workflow steps |
| GitHub Copilot | `198982749+Copilot@users.noreply.github.com` | `Copilot`, `copilot-swe-agent[bot]` | New as of 2024; pattern evolves |
| Greenkeeper (deprecated) | `support@greenkeeper.io` | `greenkeeperio-bot`, `greenkeeper[bot]` | Replaced by Snyk / Renovate but still seen in long-lived repos |
| Snyk | `snyk-bot@snyk.io` | `snyk-bot` | |
| Imgbot | `ImgBotApp@gmail.com` | `ImgBotApp`, `imgbot[bot]` | Image optimization bot |
| pre-commit.ci | `66853113+pre-commit-ci[bot]@users.noreply.github.com` | `pre-commit-ci[bot]` | Auto-fixes pre-commit hook output |
| GitHub Web Editor (online edits) | `noreply@github.com` | n/a (uses the user's login) | NOT a bot — the user edited via web UI; do not skip these even though the email is bot-like |

## Generic noreply patterns

Treat any email matching these as bot-like unless the login disambiguates:

```
*[bot]@users.noreply.github.com
*@bots.noreply.github.com
bot@*
*-bot@*
*-ci@*
ci@*
service-account@*
*@*.iam.gserviceaccount.com   (Google Cloud service accounts; common in CI)
```

The exception (`noreply@github.com` alone, no `[bot]` prefix) is GitHub's web editor — that is a real user committing through the UI. Distinguish by checking the author's `name` field too: web-editor commits have a human name; bot commits have the bot's display name like `dependabot[bot]`.

## Non-GitHub forges

| Forge | Conventions |
|---|---|
| GitLab | `[Bot]` suffix in user display name; bot user IDs are negative integers in the API; ServiceDesk bot uses `support@<gitlab.example.com>` |
| Codeberg / Forgejo | No standard bot suffix; check `is_admin` plus integration patterns; Renovate self-hosted appears as a regular user with the org's chosen handle |
| Bitbucket Cloud | App-installed integrations appear with `(Bitbucket app)` in display name; no email-pattern convention |

When the forge is non-GitHub (see `forge-adapters.md` for detection), the email-pattern check above is unreliable. Prefer a login-pattern check against the forge's documented bot accounts plus an explicit allowlist of known integrations the repo uses.

## Self-hosted / custom bots

Repos with custom automation often inherit one of these patterns; capture them in repo-local config rather than the global catalog:

- `CLAUDE.md` / `AGENTS.md` `bots:` section listing repo-local automation accounts.
- A `.github/bot-accounts.json` (convention) — list of `{login, email, why}` entries the bot guard can read.

Capabilities should fall back to the global catalog when no repo-local config exists, then merge any repo-local list on top.

## When the heuristic is wrong

Two failure modes worth knowing:

- **False positive** — a human contributor's email matches a generic pattern (`service@<their-email-provider>`). The capability skips their work as if it were a bot. Mitigation: surface the skip in the preamble so the user notices and can override.
- **False negative** — a bot uses a vanity email or runs under a personal account (common with self-hosted Renovate). The capability treats bot work as human and flags formatting issues that will be overwritten on the bot's next run. Mitigation: encourage repo-local bot config above so the catalog grows organically per repo.

The catalog itself does not auto-update; it depends on the user adding new entries as new bots appear in their workflows. Plan to revisit annually as the bot landscape changes.
