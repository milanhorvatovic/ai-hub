---
name: security-policy
description: >
  Scans, audits, and scaffolds a repository's security posture — the SECURITY.md
  disclosure policy and private reporting path, GitHub private vulnerability
  reporting and security advisories, signed commits and tags, build provenance
  / SLSA, OpenSSF Scorecard signals, and branch-protection settings. In audit
  mode it flags a missing disclosure policy or unprotected default branch and
  explains the risk; in scaffold mode it writes SECURITY.md and proposes (never
  auto-applies) the gh commands to enable protections. Triggers on "add a
  security policy", "how do people report vulns", "is my main branch
  protected", "harden this repo", or a full-repo audit.
allowed-tools: Bash Read Grep Glob Write
---

# security-policy capability

Governs how the repository handles vulnerabilities and protects its integrity:
is there a private disclosure path, are releases and history tamper-evident, and
is the default branch protected. Reads and judges by default; writes
`SECURITY.md` only on confirmation and *proposes* (never applies) settings
changes.

## Modes

- **scan** — report the security files and settings present.
- **audit** — judge posture against `../../references/oss-health-rubric.md` and OpenSSF Scorecard signals.
- **scaffold** — write `SECURITY.md` after confirmation; output `gh` commands for settings the user runs themselves.

## Input guards

- Not a git repo → stop.
- `gh` not authenticated → run the file-based checks (SECURITY.md, signing config) and mark settings-based checks (branch protection, advisories, private reporting) as `unknown — gh not available`; never fail them silently.
- Fork → branch-protection and advisory settings reflect the fork, not upstream; note this.

## Scan

Files (catalog: `../../references/convention-files.md`, Security section), citing each source:

1. Disclosure policy: `SECURITY.md`, `.github/SECURITY.md`, `docs/SECURITY.md`.
2. Dependency/secret tooling: `.github/dependabot.yaml`, `.gitleaks.toml`, `.trufflehog`, `.semgrep.yml` (deep coverage lives in the `dependency-supply-chain` and `ci-automation` capabilities; here, note presence).
3. Signing intent: `.gitattributes` / git config hints; sample `git log --show-signature -5` for signed commits; `git tag -v` for signed tags.
4. Provenance: workflow steps using `actions/attest-build-provenance`, SLSA generators, or `cosign`.

Settings (require `gh`):

- Private vulnerability reporting: `gh api repos/{owner}/{repo} --jq .security_and_analysis` and the private-reporting flag.
- Branch protection on the default branch: `gh api repos/{owner}/{repo}/branches/{default}/protection` (required reviews, required status checks, linear history, no force-push).
- Open security advisories: `gh api repos/{owner}/{repo}/security-advisories --jq 'length'` when accessible.

## Audit checks

- `security-md` — **should**. A `SECURITY.md` exists with a *private* reporting channel (GitHub private reporting, security@ email, or advisory link). A policy that says "open a public issue" for vulns → fail (defeats responsible disclosure).
- `private-vuln-reporting` — **should**. GitHub private vulnerability reporting is enabled, or `SECURITY.md` provides an equivalent private path.
- `default-branch-protected` — **should**. Default branch requires PR review and passing checks, blocks force-push, and isn't directly pushable. Public lib with no protection → fail.
- `signed-tags` — **could** (→ **should** for repos that publish releases/artifacts). Release tags are signed so consumers can verify provenance.
- `build-provenance` — **could** (→ **should** for published packages). Releases carry SLSA/attestation provenance.
- `secret-scanning` — **should**. Secret scanning / push protection enabled, or a `gitleaks`-style check runs in CI.
- `no-secrets-in-history` — **must**. No live credentials committed. If a scan suggests any, treat as `must` and point to rotation + history-rewrite (don't perform it here).

Score and present per `../../references/output-format.md`. Mirror OpenSSF Scorecard naming where it overlaps (`Branch-Protection`, `Signed-Releases`, `Vulnerabilities`, `Token-Permissions`).

## Scaffold

`SECURITY.md` — write after confirmation, tailored to the repo's reporting choice:

```markdown
# Security Policy

## Supported versions
| Version | Supported |
|---|---|
| <latest> | ✅ |
| < <latest> | ❌ |

## Reporting a vulnerability
Please report vulnerabilities privately via
<GitHub private vulnerability reporting | security@<domain> | advisory link>.
Do **not** open a public issue for security problems.

We aim to acknowledge within <N> business days and to provide a fix or
mitigation timeline after triage. Coordinated disclosure is appreciated.
```

House style places it at `.github/SECURITY.md`. Fill the supported-versions
table from the repo's release/branch reality, not a guess.

Settings — **propose, never apply** (the user runs these):

```bash
# Enable private vulnerability reporting
gh api -X PUT repos/{owner}/{repo}/private-vulnerability-reporting

# Protect the default branch (review + checks + no force-push)
gh api -X PUT repos/{owner}/{repo}/branches/{default}/protection \
  --input protection.json   # show the user the JSON first
```

Always show the exact command and what it changes; let the user execute it.

## Edge cases

- **No published artifact** — relax `signed-tags` / `build-provenance` to `could`; a disclosure path still matters.
- **Org-level policy** — a `.github` org repo may supply `SECURITY.md` for all repos; detect and don't duplicate.
- **Monorepo** — one disclosure policy at root usually suffices; note if components need separate contacts.
- **Suspected committed secret** — never echo the secret; report location + advise rotation and history rewrite via the appropriate dedicated tooling; do not attempt the rewrite here.

## Anti-patterns

- Don't apply branch protection, private-reporting, or any setting automatically — output the command.
- Don't write a `SECURITY.md` that routes vulnerabilities to public issues.
- Don't pass `private-vuln-reporting` or `default-branch-protected` as satisfied when `gh` is unavailable — mark them `unknown`.
- Don't print or commit any secret you find while scanning.
