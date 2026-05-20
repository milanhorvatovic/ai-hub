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

Governs whether the project is verifiable: are there tests, do they run automatically, and is coverage visible. **Toolkit, not turnkey** — the test _content_ (unit / integration / acceptance / E2E) is project-specific and the project owns it; this capability provides the runner and coverage _wiring_, the layout, and per-test-type setup/maintenance guidance. Reads and judges by default; writes test/coverage config and harness scaffolding only on confirmation — never the tests themselves.

## Modes

- **scan** — report the framework, layout, coverage config, and CI test step.
- **audit** — judge verifiability against `../../references/oss-health-rubric.md`.
- **scaffold** — write a test-runner config and coverage config after confirmation.

## Inputs & guards

- Not a git repo → stop.
- Detect the stack first; a docs/data repo with no code has nothing to test — relax accordingly.
- Toolkit boundary: scaffold the runner/coverage wiring and the test layout; never write the project's tests. The composable `test`/`coverage` CI blocks come from the automation-baseline capability; hardening lives in ci-automation.
- Don't run the test suite as part of audit unless asked — scanning configs is enough to judge setup.

## Scan

Sources (catalog: `../../references/convention-files.md`, Tests section), citing each:

1. Framework + config: `pytest.ini` / `[tool.pytest.ini_options]`, `jest.config.*` / `vitest.config.*`, `*_test.go`, `#[cfg(test)]` / `cargo test`, `phpunit.xml`, `.rspec`.
2. Layout: a `tests/` or `test/` tree, co-located `*.test.ts` / `*_test.go`, naming conventions.
3. Coverage: `.coveragerc` / `[tool.coverage]`, jest `coverageThreshold`, `codecov.yml` / `.codecov.yml`, coverage badges.
4. CI: a test step in workflows (`gh api` or read `.github/workflows/*`); whether it runs on `pull_request`.

## Audit

Checks follow the schema in `../../references/oss-health-rubric.md` (`id` — **severity** [· scorecard: Name]. criterion. why):

- `tests-present` — **must** (code repos) · scorecard: CI-Tests. Fail when a repo that ships code has no test suite. Untested published code can't be changed safely or trusted by consumers.
- `tests-run-in-ci` — **should** · scorecard: CI-Tests. Fail when tests exist but don't run on pull requests. Tests that aren't automated don't catch regressions.
- `coverage-measured` — **could** (→ **should** for libraries). Pass when coverage is measured and reported. Reveals untested paths.
- `coverage-gated` — **could**. Pass when a coverage threshold gates CI. Prevents silent coverage erosion (pick a realistic threshold, don't over-prescribe).
- `test-layout-conventional` — **could**. Pass when tests follow the ecosystem's conventional layout/naming. Makes them discoverable and runnable by default tooling.

## Test types (the project owns these)

The skill helps set up and maintain each layer; it does not write the tests. Guidance per type, so the maintainer knows what to put where:

- **unit** — fast, isolated, no I/O; the default `tests/` layer. Maintain: keep them deterministic and quick; they gate every PR.
- **integration** — exercise real boundaries (DB, filesystem, HTTP) with controlled fixtures/containers. Maintain: isolate via a separate task/marker so they can run apart from unit tests; provide service containers in CI.
- **acceptance** — assert behavior against requirements/specs from the user's view. Maintain: keep them readable as living documentation; tie to issues/specs.
- **E2E** — drive the whole system (browser/CLI/API end to end). Maintain: keep them few and stable; they're slow and flaky-prone — run on a schedule or pre-release rather than every PR.

Recommend splitting these into separate runner targets/markers so CI can run the fast layers on every PR and the slow layers (E2E) on a schedule.

## Scaffold

Provide the _wiring_, not the tests. From `references/scaffold-templates.md`, write after confirmation (tailored to the framework, or the ecosystem default):

- the **runner config** (pytest / vitest / …) and a `tests/` layout with per-type subdirs or markers;
- the **coverage config** (measurement + optional, realistic gate);
- optional **harness skeletons** clearly marked as placeholders (a fixture file, an empty E2E spec) — never real assertions.

The `test` and `coverage` CI jobs that run all this are composable building blocks from the automation-baseline capability; wire to them rather than duplicating a workflow, and harden via ci-automation.

## Output

Report per `../../references/output-format.md`: scan emits the testing inventory (framework, layout, coverage, CI) with sources; audit emits severity-tagged findings, the domain score, and a `scaffold` offer for each unmet check.

## Edge cases

- **Docs/data/config repo** — no code to test; relax `tests-present` to not-applicable (skip, don't fail).
- **Examples-only repo** — a smoke test that the examples run may be the right bar; don't demand a full suite.
- **Existing high coverage with no gate** — `coverage-gated` stays `could`; don't push a number the maintainer didn't choose.
- **Flaky/slow suites** — out of scope to fix here; note if CI clearly skips tests.

## Anti-patterns

- Don't write the project's tests — provide wiring, layout, and guidance; the project owns the assertions.
- Don't run the suite during audit unless asked — read the configs.
- Don't prescribe a specific coverage percentage as a hard requirement.
- Don't duplicate the CI workflow — the test/coverage blocks are the automation-baseline capability's; hardening is ci-automation's.
- Don't overwrite an existing test/coverage config without a diff.
