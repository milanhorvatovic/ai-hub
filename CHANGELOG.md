# Changelog

All notable changes to the skills in this repository are documented here, grouped by skill. The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/); each skill is versioned with [Semantic Versioning](https://semver.org/spec/v2.0.0.html), and the repository cuts dated CalVer (`vYYYY.MM.MICRO`) release-train snapshots over the set. This file is updated by hand when a release is cut — see the catalog-cut runbook in [CONTRIBUTING.md](CONTRIBUTING.md) and [docs/adr/0001-release-and-versioning.md](docs/adr/0001-release-and-versioning.md).

## v2026.05.0 — 2026-05-24 (initial catalog)

Baseline snapshot establishing the release process. This entry backfills the complete per-skill version history merged through #12.

### coding-principles

- **1.0.0** — 2026-05-20 (#4): initial release — implementation-discipline router with on-demand language capabilities and a review workflow.

### docs-steward

- **1.1.0** — 2026-05-20 (#5): default to Prettier with a markdownlint lint pass.
- **1.0.0** — 2026-05-19 (#2): initial release — markdown stewardship orchestrating external formatters plus yamllint, emitting NDJSON findings.

### git-toolkit

- **1.1.0** — 2026-05-21 (#8): harden untrusted-content ingestion against indirect prompt injection (Snyk W011).
- **1.0.0** — 2026-05-20 (#3): initial release — git + GitHub change-narration router across the branch/commit/PR/release lifecycle.

### oss-repository-conventions

- **1.0.0** — 2026-05-22 (#9): initial release — OSS repository scan/audit/scaffold router across fourteen domain capabilities, including release and versioning.
