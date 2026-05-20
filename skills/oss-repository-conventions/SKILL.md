---
name: oss-repository-conventions
description: >
  Stewards an open-source repository toward and along a top-notch standard.
  Operates in three modes — scan (report what conventions and health files a
  repo declares), audit (score the repo against OSS best practice and the
  maintainer's house style, flagging gaps with severity), and scaffold (draft
  the missing files on request, one confirmation per file). Routes to
  capabilities covering licensing, contributing, code of conduct, governance,
  community health, security policy, repository infrastructure, dev setup,
  code style, testing and quality, CI and automation, dependency and supply
  chain, release and versioning, and documentation. Reports and proposes;
  authoring of individual commits, PRs, branches, and release notes is out of
  scope (that is the change-narration domain). Triggers when the user asks to
  audit / set up / harden / level up an OSS repo, "what is this repo missing",
  "make this repo top-notch", "add a SECURITY policy / license / CONTRIBUTING",
  "score this repo's health", first-touch onboarding, or invokes
  /oss-repository-conventions.
allowed-tools: Bash Read Grep Glob Write Edit
metadata:
  version: "0.3.0"
---

# oss-repository-conventions

## Purpose

Helps a maintainer reach and hold a high-quality open-source repository. Routes each request to the capability for the domain in question, and runs each in the mode the request implies — scan, audit, or scaffold.

## Operating modes

Every capability supports the same three modes; the router picks the one the request implies, defaulting to `audit` when ambiguous.

| Mode | Question it answers | Writes files? |
|---|---|---|
| **scan** | "What does this repo declare today?" | No |
| **audit** | "How does it measure up, and what's missing or weak?" | No |
| **scaffold** | "Create the missing/upgraded file." | Yes — one confirmation per file |

- **scan** is the read-only inventory + summary the skill has always done — extract declared rules, cite the file of truth, flag conflicts.
- **audit** layers judgment on the scan: score against `references/oss-health-rubric.md` and `references/house-style.md`, classify each gap `must` / `should` / `could`, and explain *why* it matters for an OSS project.
- **scaffold** acts on an audit finding: propose file content from the templates a capability carries, show it, and write only on explicit confirmation. Never bulk-writes; never overwrites an existing file without showing a diff first.

## Scope

- **In scope:** the repository as a subject — its legal, community, security, infrastructure, automation, release-process, and documentation conventions, and the files that declare them.
- **Out of scope:** authoring individual changes — commit messages, PR descriptions, branch names, and the release *notes* for a specific version. Those belong to the change-narration domain. This skill governs the *release process* (versioning policy, changelog format, release automation), not the prose of any one release.

## Architecture

Two layers, following the repo's router pattern:

- **Router** (this `SKILL.md`): contract, modes, principles, capability routing. Loads always.
- **Capabilities** (`capabilities/<name>/capability.md`): one per domain, self-sufficient — load just the one whose trigger matches. Each declares its own `allowed-tools`; this router's `allowed-tools` is the union.

Shared references at the skill root hold the scan catalog, the audit rubric, the maintainer's house style, and the output schema. Capabilities link to them via `../../references/<file>.md` rather than duplicating.

## Principles

- **Repo conventions override generic defaults.** A repo that declares its own convention (in `CLAUDE.md`, `AGENTS.md`, `CONTRIBUTING.md`, a lint/CI config, or a template) is the source of truth; the generic OSS baseline applies only where the repo is silent. Precedence: agent-instruction file > `CONTRIBUTING.md` / docs > tool config > generic baseline.
- **House style sits above the generic baseline.** `references/house-style.md` captures conventions distilled from the maintainer's existing OSS repos (agent-instruction files, `mise` tool-pinning, `RELEASE_NOTES_TEMPLATE.md`, Keep-a-Changelog, Dependabot, CODEOWNERS, PR template). Audit prefers the house pattern over an equally-valid generic alternative so a new repo matches the rest of the fleet.
- **Report, judge, then — only on request — write.** scan and audit never modify the repo. scaffold writes, but one file at a time, behind an explicit confirmation, after showing the content.
- **Severity is honest.** A missing `LICENSE` on a public repo is `must`; a missing `FUNDING.yml` is `could`. The rubric, not enthusiasm, sets severity. Don't inflate.
- **Cite the file of truth.** Every scan/audit line names the file (and line, where useful) it was read from, or marks a finding `(inferred from git history)` / `(not declared)`. Silence in a config is not proof a convention is unused — it may be tribal knowledge.
- **Never auto-publish repo settings.** Branch protection, default branch, repo topics, and other settings reachable via `gh api` are *proposed* as commands, never applied automatically.

## Capability routing

Each row routes to a self-sufficient capability. The path column is the file to load.

### Legal, security & governance

| Capability | Covers | Path |
|---|---|---|
| licensing | LICENSE selection & SPDX, dual/multi-licensing, per-file headers, REUSE compliance, NOTICE, license compatibility | capabilities/licensing/capability.md |
| security-policy | SECURITY.md & private disclosure, advisories, signed commits/tags, provenance/SLSA, OpenSSF Scorecard signals, branch protection | capabilities/security-policy/capability.md |
| code-of-conduct | CODE_OF_CONDUCT (Contributor Covenant), enforcement contact | capabilities/code-of-conduct/capability.md |
| governance | CODEOWNERS review routing, MAINTAINERS/OWNERS/AUTHORS, GOVERNANCE decision model | capabilities/governance/capability.md |

### Contribution & community

| Capability | Covers | Path |
|---|---|---|
| contributing | CONTRIBUTING, DCO/CLA & sign-off, dev onboarding, good-first-issue labels | capabilities/contributing/capability.md |
| community-health | Issue/PR templates & forms, SUPPORT, FUNDING, discussions, triage labels | capabilities/community-health/capability.md |

### Engineering & infrastructure

| Capability | Covers | Path |
|---|---|---|
| repo-infrastructure | Git hygiene files (.gitignore/.gitattributes/.editorconfig/.mailmap) and repo settings (default branch, topics, merge policy) | capabilities/repo-infrastructure/capability.md |
| dev-setup | Toolchain pinning (mise/.tool-versions), dev/test deps, one-command bootstrap, .env.example, devcontainer | capabilities/dev-setup/capability.md |
| code-style | Per-language formatters & linters, pre-commit/lefthook hooks, style enforced in CI | capabilities/code-style/capability.md |
| testing-quality | Test framework & layout, tests run in CI, coverage measured/gated | capabilities/testing-quality/capability.md |

### Automation & supply chain

| Capability | Covers | Path |
|---|---|---|
| ci-automation | Actions workflows, build/test on PRs, least-privilege tokens, SHA-pinned actions, OIDC, scheduled jobs | capabilities/ci-automation/capability.md |
| dependency-supply-chain | Dependabot/Renovate, lockfiles, dependency pinning, vulnerability monitoring, SBOM | capabilities/dependency-supply-chain/capability.md |

### Release & documentation

| Capability | Covers | Path |
|---|---|---|
| release-versioning | SemVer policy, Keep-a-Changelog, release automation, tag/release consistency, support/deprecation policy | capabilities/release-versioning/capability.md |
| documentation | README structure & badges, docs site, ADRs, runnable examples, agent-instruction files | capabilities/documentation/capability.md |

### Alphabetic index (fallback)

| Capability | Path |
|---|---|
| ci-automation | capabilities/ci-automation/capability.md |
| code-of-conduct | capabilities/code-of-conduct/capability.md |
| code-style | capabilities/code-style/capability.md |
| community-health | capabilities/community-health/capability.md |
| contributing | capabilities/contributing/capability.md |
| dependency-supply-chain | capabilities/dependency-supply-chain/capability.md |
| dev-setup | capabilities/dev-setup/capability.md |
| documentation | capabilities/documentation/capability.md |
| governance | capabilities/governance/capability.md |
| licensing | capabilities/licensing/capability.md |
| release-versioning | capabilities/release-versioning/capability.md |
| repo-infrastructure | capabilities/repo-infrastructure/capability.md |
| security-policy | capabilities/security-policy/capability.md |
| testing-quality | capabilities/testing-quality/capability.md |

## Shared references

| File | Holds |
|---|---|
| `references/convention-files.md` | The scan catalog — every file path the skill checks, bucketed by domain |
| `references/oss-health-rubric.md` | The audit rubric — per-domain checks, severity, and how the health score is computed |
| `references/house-style.md` | The maintainer's distilled conventions and recurring gaps, used to bias audit recommendations |
| `references/output-format.md` | Canonical markdown report shape for scan and audit output, with a per-finding NDJSON line |

## Full-repo audit

When the user asks to audit / level-up / score the whole repo (not one domain), run each built capability in `audit` mode, then aggregate per `references/output-format.md`: one section per domain, a roll-up health score from `references/oss-health-rubric.md`, and a prioritized `must` → `should` → `could` action list. Offer to `scaffold` the `must` items.

## Anti-patterns

- Don't write files in scan or audit mode — those modes only read and report.
- Don't scaffold in bulk or overwrite silently — one file, one confirmation, diff shown for any existing file.
- Don't apply repo settings (`gh api ... -X PATCH/PUT`) automatically — propose the command.
- Don't inflate severity to push a recommendation; the rubric governs.
- Don't author commit messages, PR bodies, branch names, or a specific release's notes — that's the change-narration domain; this skill stops at the *process* and the declared conventions.
- Don't treat a silent config as proof a convention is absent — mark it inferred or undeclared, never asserted.
