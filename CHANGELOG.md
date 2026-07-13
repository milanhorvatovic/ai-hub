# Changelog

> **Frozen pre-automation record.** From 2026-07-13 onward, release-please writes each skill's history to its own `skills/<name>/CHANGELOG.md` (standard monorepo layout), not to this file — a single root changelog cannot be produced from per-skill packages, see [docs/adr/0001-release-and-versioning.md](docs/adr/0001-release-and-versioning.md) and its 2026-07-13 amendment. This file is retained as the frozen baseline of catalog history up to the first automated release; the CalVer release-train (`vYYYY.MM.MICRO`) remains the catalog-wide view, presented in GitHub Releases.

This baseline documents the skills as of the initial catalog, grouped by skill. The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/); each skill is versioned with [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
