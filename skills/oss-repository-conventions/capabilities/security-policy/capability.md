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

Governs how the repository handles vulnerabilities and protects its integrity: is there a private disclosure path, are releases and history tamper-evident, and is the default branch protected. Reads and judges by default; writes `SECURITY.md` only on confirmation and _proposes_ (never applies) settings changes.

## Modes

- **scan** — report the security files and settings present.
- **audit** — judge posture against `../../references/oss-health-rubric.md` and OpenSSF Scorecard signals.
- **scaffold** — write `SECURITY.md` after confirmation; output `gh` commands for settings the user runs themselves.

## Inputs & guards

- Not a git repo → stop.
- `gh` not authenticated → run the file-based checks (SECURITY.md, signing config) and mark settings-based checks (branch protection, advisories, private reporting) as `unknown — gh not available`; never fail them silently.
- Fork → branch-protection and advisory settings reflect the fork, not upstream; note this.

## Scan

Files (catalog: `../../references/convention-files.md`, Security section), citing each source:

1. Disclosure policy: `SECURITY.md`, `.github/SECURITY.md`, `docs/SECURITY.md`; and `SECURITY-INSIGHTS.yml` (OpenSSF Security Insights — machine-readable security metadata).
2. Dependency/secret tooling: `.github/dependabot.yaml`, `.gitleaks.toml`, `.trufflehog`, `.semgrep.yml` (deep coverage lives in the dependency-supply-chain and ci-automation capabilities; here, note presence).
3. Signing intent: `.gitattributes` / git config hints; sample `git log --show-signature -5` for signed commits; `git tag -v` for signed tags.
4. Provenance: workflow steps using `actions/attest-build-provenance`, SLSA generators, or `cosign`.

Settings (require `gh`):

- Private vulnerability reporting: `gh api repos/{owner}/{repo} --jq .security_and_analysis` and the private-reporting flag.
- Branch protection on the default branch: `gh api repos/{owner}/{repo}/branches/{default}/protection` (required reviews, required status checks, linear history, no force-push).
- Open security advisories: `gh api repos/{owner}/{repo}/security-advisories --jq 'length'` when accessible.

## Audit

Checks follow the schema in `../../references/oss-health-rubric.md` (`id` — **severity** [· scorecard: Name]. criterion. why):

- `no-secrets-in-history` — **must** · scorecard: Vulnerabilities. Fail when a scan finds live committed credentials. Leaked secrets are an active compromise; point to rotation + history rewrite (don't perform it here).
- `security-md` — **should**. Fail when no `SECURITY.md`, or when it routes vulnerabilities to public issues; pass when it gives a _private_ channel (GitHub private reporting, security@ email, advisory link). Public disclosure defeats responsible reporting.
- `private-vuln-reporting` — **should**. Fail when GitHub private vulnerability reporting is off and `SECURITY.md` offers no private path. Reporters need a non-public way in.
- `default-branch-protected` — **should** · scorecard: Branch-Protection. Fail when the default branch allows direct pushes/force-push or requires no review/checks — via classic protection **or** a ruleset (recognize either). Grade depth per `../../references/branch-protection.md` (required checks, reviews + code-owner, conversation resolution, linear history, signed commits, no force-push). Unprotected main lets unreviewed or rewritten history land.
- `tag-protection` — **could** (→ **should** when the repo publishes releases). Pass when release tags (`v*`) are protected from deletion/overwrite by a tag ruleset, so a published release can't be silently re-pointed. See `../../references/branch-protection.md`.
- `secret-scanning` — **should**. Pass when secret scanning / push protection is on, or a gitleaks-style check runs in CI. Catches credentials before they merge.
- `signed-tags` — **could** (→ **should** when the repo publishes releases) · scorecard: Signed-Releases. Pass when release tags are signed (`git tag -v`). Lets consumers verify provenance. See `../../references/commit-signing.md`.
- `signed-commits` — **could** (→ **should** when the branch requires signatures). Pass when commits are signed and show Verified (GPG / SSH / gitsign) and — where signatures are required — automations sign too (API/App commits are auto-verified). An unsigned bot commit is a gap on a signature-required branch. See `../../references/commit-signing.md`.
- `build-provenance` — **could** (→ **should** for published packages). Grade by **SLSA build level**: L0 none → L1 provenance exists (e.g. `actions/attest-build-provenance` / a SLSA generator) → L2 provenance signed by a hosted build service → L3 hardened, non-falsifiable build. Pass the `could` bar at L1+; aim L2+ for distributed artifacts. Tamper-evidence for the artifact supply chain. Report the level, not just present/absent. (No dedicated OpenSSF Scorecard check maps to build provenance — `signed-tags` carries the Signed-Releases signal; grade this one by SLSA level instead.)
- `security-insights` — **could**. Pass when `SECURITY-INSIGHTS.yml` (OpenSSF Security Insights spec) publishes machine-readable security metadata — policy URL, contacts, dependency/vulnerability practices. Lets tooling and consumers assess posture without scraping prose.
- `two-factor-enforced` — **should**. Pass when 2FA is required for the org/repo and for publishing where the registry supports it (npm and PyPI now require it for many packages). Account takeover is a top supply-chain attack vector. Org-level setting via `gh api` — mark `unknown` without org access; don't pass it silently.
- `container-image-hardening` — **could** (when the repo ships a container image). Pass when the image pins its base by digest, runs as non-root, is scanned (Trivy / Grype), and is signed (cosign) with an attached SBOM. A published image is its own artifact supply chain.
- `iac-scanning` — **could** (when the repo contains infrastructure-as-code). Pass when IaC (Terraform / CloudFormation / Kubernetes manifests) is scanned for misconfiguration (checkov / tfsec / KICS) in CI. Misconfigured IaC is a common breach vector.
- `fuzzing` — **could** (→ **should** for libraries parsing untrusted input) · scorecard: Fuzzing. Pass when continuous fuzzing is set up (OSS-Fuzz, cargo-fuzz, go-fuzz, atheris, libFuzzer). Fuzzing catches memory/parsing bugs that example-based tests miss.
- `threat-model` — **could** (security-maturity / gold-tier). Pass when a threat model is documented (assets, trust boundaries, mitigations). Surfaces design-level risk that file/setting checks can't.

## Scaffold

`SECURITY.md` — write after confirmation from `references/security-md.template.md`, tailored to the repo's reporting choice and real supported-versions (don't guess the table). House style places it at `.github/SECURITY.md`.

Settings — **propose, never apply** (the user runs these); show the exact command and what it changes:

```bash
# Enable private vulnerability reporting
gh api -X PUT repos/{owner}/{repo}/private-vulnerability-reporting

# Protect the default branch (review + checks + no force-push)
gh api -X PUT repos/{owner}/{repo}/branches/{default}/protection \
  --input branch-protection.example.json   # show + tailor the JSON first
```

The protection payload template is `references/branch-protection.example.json`.

## Output

Report per `../../references/output-format.md`: scan emits the security inventory (files + settings) with sources; audit emits severity-tagged findings (Scorecard-aligned ids), the domain score, and a `scaffold` offer or the exact `gh` command for each unmet `must` / `should`.

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
