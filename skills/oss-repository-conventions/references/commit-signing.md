# Commit & tag signing

Whether commits and tags are cryptographically signed and show as **Verified** on GitHub — for both human developers and automations.

## Developer signing

| Method | How | Notes |
| --- | --- | --- |
| **GPG** | `git config user.signingkey <key>` + `commit.gpgsign true`; upload the public key to GitHub | classic; key-management overhead |
| **SSH** | `git config gpg.format ssh` + `user.signingkey ~/.ssh/id_ed25519.pub`; add it as a _signing_ key on GitHub | reuses an existing SSH key; simplest |
| **gitsign (Sigstore)** | keyless signing via an OIDC identity (`gpg.format x509` + gitsign) | no long-lived key; ideal for ephemeral / CI identities |

A commit shows **Verified** when its signature matches a key/identity GitHub associates with the author. Sign tags too: `git tag -s vX.Y.Z`.

## Requiring signatures

Enforce via the branch-protection / ruleset "**require signed commits**" control (see `branch-protection.md`). Pair it with signed, protected release tags so consumers can verify provenance end to end.

## Automation signing

Bots and CI should produce **verified** commits too — an unsigned bot commit is a gap when the branch requires signatures:

- **GitHub API** (`createCommitOnBranch` GraphQL, the contents REST API, or web-UI edits): commits are **automatically verified** by GitHub's own key — no key to manage. Best default for bots that commit via the API.
- **GitHub App**: API commits attributed to the App are verified as the App.
- **gitsign keyless** in CI: signs with the workflow's OIDC identity (Sigstore) — verifiable, no stored key.
- **Bot GPG/SSH key**: a dedicated key stored as a secret; works, but adds rotation burden — prefer the API/App or gitsign.

Tie the identity choice to `automation-identity.md`: a GitHub App committing via `createCommitOnBranch` gets scoped identity **and** verified commits at once.

## Auditing

- Sample `git log --show-signature -20` for signed commits and `git tag -v <tag>` for signed tags.
- When the branch requires signatures, confirm automations sign too (otherwise their commits are rejected or land unverified).
- Mark `unknown` when keys/settings aren't inspectable without `gh`.
