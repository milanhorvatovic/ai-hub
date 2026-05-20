---
name: testing-quality
description: >
  Scans, audits, and scaffolds a repository's testing setup — the test framework
  and conventional layout, whether tests run in CI on pull requests, and whether
  coverage is measured and (optionally) gated. Audit flags a code repo with no
  tests (a must) and tests that don't run in CI; scaffold writes a test-runner
  config and coverage config. Triggers on "set up tests", "add coverage", "do
  tests run in CI", "gate on coverage", or a full-repo audit.
allowed-tools: Bash Read Grep Glob Write
---

# testing-quality capability

Governs whether the project is verifiable: are there tests, do they run
automatically, and is coverage visible. Reads and judges by default; writes test
and coverage config only on confirmation.

## Modes

- **scan** — report the framework, layout, coverage config, and CI test step.
- **audit** — judge verifiability against `../../references/oss-health-rubric.md`.
- **scaffold** — write a test-runner config and coverage config after confirmation.

## Inputs & guards

- Not a git repo → stop.
- Detect the stack first; a docs/data repo with no code has nothing to test — relax accordingly.
- The CI *workflow* that runs tests is the ci-automation capability's file; here, audit whether tests run in CI and scaffold the runner/coverage config.
- Don't run the test suite as part of audit unless asked — scanning configs is enough to judge setup.

## Scan

Sources (catalog: `../../references/convention-files.md`, Tests section), citing each:

1. Framework + config: `pytest.ini` / `[tool.pytest.ini_options]`, `jest.config.*` / `vitest.config.*`, `*_test.go`, `#[cfg(test)]` / `cargo test`, `phpunit.xml`, `.rspec`.
2. Layout: a `tests/` or `test/` tree, co-located `*.test.ts` / `*_test.go`, naming conventions.
3. Coverage: `.coveragerc` / `[tool.coverage]`, jest `coverageThreshold`, `codecov.yml` / `.codecov.yml`, coverage badges.
4. CI: a test step in workflows (`gh api` or read `.github/workflows/*`); whether it runs on `pull_request`.

## Audit

Checks follow the schema in `../../references/oss-health-rubric.md`
(`id` — **severity** [· scorecard: Name]. criterion. why):

- `tests-present` — **must** (code repos) · scorecard: CI-Tests. Fail when a repo that ships code has no test suite. Untested published code can't be changed safely or trusted by consumers.
- `tests-run-in-ci` — **should** · scorecard: CI-Tests. Fail when tests exist but don't run on pull requests. Tests that aren't automated don't catch regressions.
- `coverage-measured` — **could** (→ **should** for libraries). Pass when coverage is measured and reported. Reveals untested paths.
- `coverage-gated` — **could**. Pass when a coverage threshold gates CI. Prevents silent coverage erosion (pick a realistic threshold, don't over-prescribe).
- `test-layout-conventional` — **could**. Pass when tests follow the ecosystem's conventional layout/naming. Makes them discoverable and runnable by default tooling.

## Scaffold

Templates live in `references/scaffold-templates.md` (pytest + coverage config,
vitest config). Write after confirmation, tailored to the framework in use (or
the ecosystem default if none): the runner config, a `tests/` layout, and a
coverage config. The CI step that runs them is scaffolded by the ci-automation
capability; reference it rather than duplicating the workflow here.

## Output

Report per `../../references/output-format.md`: scan emits the testing inventory (framework, layout, coverage, CI) with sources; audit emits severity-tagged findings, the domain score, and a `scaffold` offer for each unmet check.

## Edge cases

- **Docs/data/config repo** — no code to test; relax `tests-present` to not-applicable (skip, don't fail).
- **Examples-only repo** — a smoke test that the examples run may be the right bar; don't demand a full suite.
- **Existing high coverage with no gate** — `coverage-gated` stays `could`; don't push a number the maintainer didn't choose.
- **Flaky/slow suites** — out of scope to fix here; note if CI clearly skips tests.

## Anti-patterns

- Don't run the suite during audit unless asked — read the configs.
- Don't prescribe a specific coverage percentage as a hard requirement.
- Don't duplicate the CI workflow — that's the ci-automation capability.
- Don't overwrite an existing test/coverage config without a diff.
