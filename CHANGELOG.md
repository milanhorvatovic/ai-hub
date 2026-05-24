# Changelog

All notable changes to the skills in this repository are documented here, grouped by skill. The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/); each skill is versioned with [Semantic Versioning](https://semver.org/spec/v2.0.0.html), and the repository cuts dated CalVer (`vYYYY.MM.MICRO`) release-train snapshots over the set. From the first automated release onward, release-please maintains the per-skill sections below; see [docs/adr/0001-release-and-versioning.md](docs/adr/0001-release-and-versioning.md).

## v2026.05.0 — 2026-05-24 (initial catalog)

Baseline snapshot establishing the release process. Versions reflect each skill's state as merged through #12; this entry backfills real history and is the seed from which release-please takes over.

### coding-principles 1.0.0

- Initial release: implementation-discipline router with on-demand language capabilities and a review workflow.

### docs-steward 1.1.0

- Markdown stewardship: orchestrates external formatters plus yamllint, emits NDJSON findings, and defaults to Prettier with a markdownlint lint pass.

### git-toolkit 1.1.0

- git + GitHub change-narration router across the branch/commit/PR/release lifecycle, with hardened untrusted-content ingestion.

### oss-repository-conventions 1.0.0

- OSS repository scan/audit/scaffold router across fourteen domain capabilities, including release and versioning.
