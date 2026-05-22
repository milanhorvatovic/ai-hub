---
name: code-style
description: >
  Scans, audits, and scaffolds a repository's code-style enforcement — the
  per-language formatters and linters (ruff/black, eslint/prettier/biome, gofmt/
  golangci-lint, rustfmt/clippy, …), whether style runs in CI or pre-commit (not
  just optionally local), and whether the configs are consistent (one formatter
  per language, aligned with .editorconfig). Audit flags an unformatted/unlinted
  language and style that isn't enforced anywhere; scaffold writes a formatter/
  linter config and a pre-commit config. Triggers on "set up a linter/formatter",
  "enforce code style", "add pre-commit hooks", or a full-repo audit.
allowed-tools: Bash Read Grep Glob Write
---

# code-style capability

Governs how code style is configured and enforced — not how individual code is written. Is there a formatter and linter per language, and does style actually run somewhere automated rather than relying on goodwill. Reads and judges by default; writes style configs only on confirmation.

## Modes

- **scan** — report the formatters, linters, and hooks configured.
- **audit** — judge enforcement against `../../references/oss-health-rubric.md`.
- **scaffold** — write a formatter/linter config and pre-commit config after confirmation.

## Inputs & guards

- Not a git repo → stop.
- Detect the languages present first; only audit style for languages the repo actually contains.
- This capability covers style _configuration and enforcement_, not the act of writing code or applying principles to a change.
- Don't run formatters/linters that would modify the tree — propose the command.

## Languages

Detect per `../../references/language-support.md`. Formatter/linter support:

- **First-class:** Python (ruff / black), JS/TS (prettier, eslint or biome), Go (gofmt / golangci-lint), Rust (rustfmt / clippy), Swift (swift-format / swiftlint), Objective-C / C / C++ (clang-format), Ruby (rubocop).
- **Recognized:** Java / Kotlin (spotless / ktlint), PHP (php-cs-fixer) — name the tool, don't scaffold its config.
- **Unknown:** recommend only `.editorconfig` (whitespace/charset baseline) and pre-commit hygiene hooks; never invent a language-specific formatter.
- **Infra & config (lint these too when present):** shell (shellcheck + shfmt), `Dockerfile` (hadolint), GitHub Actions workflows (actionlint), YAML (yamllint), TOML (taplo) — most repos carry these alongside the primary language.

## Scan

Sources (catalog: `../../references/convention-files.md`, Code style section), citing each:

1. Formatters: `.prettierrc*` / `biome.json`, `[tool.black]` / `[tool.ruff.format]` in `pyproject.toml`, `gofmt`/`gofumpt` usage, `rustfmt.toml`, `.swift-format`.
2. Linters: `.eslintrc*` / `eslint.config.*`, `[tool.ruff]` / `.flake8` / `[tool.mypy]`, `.golangci.yml`, `clippy.toml`, `.rubocop.yml`.
3. Enforcement: `.pre-commit-config.yaml`, `lefthook.yml`, `.husky/`; and lint/format steps in CI workflows (deep CI coverage is the ci-automation capability).
4. Consistency: `.editorconfig` settings vs the formatter's (indent, EOL); multiple overlapping formatters for one language.

## Audit

Checks follow the schema in `../../references/oss-health-rubric.md` (`id` — **severity** [· scorecard: Name]. criterion. why):

- `formatter-configured` — **should** (per language present). Fail when a major language has no formatter. Without one, style is subjective and diffs fill with reformatting noise.
- `linter-configured` — **should** (per language present). Fail when there's no linter catching bugs/smells. Linters prevent a class of defects before review.
- `style-enforced` — **should**. Fail when format/lint isn't run in CI or a pre-commit hook (optional-local-only doesn't count). Unenforced style decays.
- `pre-commit-hooks` — **could**. Pass when a pre-commit/lefthook config runs format+lint before commit. Catches issues at the earliest point.
- `config-consistent` — **could**. Pass when there's one formatter per language and `.editorconfig` agrees with it. Conflicting formatters cause churn.

## Scaffold

Templates live in `references/scaffold-templates.md` (pre-commit config; ruff and prettier/biome starting configs). Write after confirmation, tailored to the languages present:

- Pick **one** formatter per language (house-style-friendly: ruff for Python, prettier or biome for JS/TS) — don't stack overlapping tools.
- Align the config's indent/EOL with `.editorconfig` (the repo-infrastructure capability owns that file).
- Add a `.pre-commit-config.yaml` and/or a CI lint step so style is enforced (CI wiring is the ci-automation capability).

## Output

Report per `../../references/output-format.md`: scan emits the per-language style inventory and where (if anywhere) it's enforced; audit emits severity-tagged findings, the domain score, and a `scaffold` offer for each unmet check.

## Edge cases

- **Polyglot repo** — audit each language independently; partial coverage is a per-language finding.
- **Generated/vendored code** — exclude it from formatter/linter scope; flag if it's being linted by accident.
- **Existing strict config** — don't loosen a deliberate stricter setup; only flag genuine gaps.
- **Docs/data repo** — relax to `could`; a markdown/yaml linter may still apply.

## Anti-patterns

- Don't run formatters/linters that rewrite files — propose the command.
- Don't stack two formatters for the same language.
- Don't conflate this with code-authoring discipline — it configures and enforces, it doesn't write the code.
- Don't overwrite an existing style config without a diff.
