---
name: pr-checks-summary
description: >
  Inspects a PR's CI check results, fetches logs for failed checks, and
  produces an interpretive summary — not just a raw status list. Classifies
  failure types (test, lint, build, deploy, security scan, type-check),
  surfaces the most likely fix-pattern when recognizable, and groups
  related failures. Distinct from `gh pr checks` (raw list). Triggers when
  the user asks "what's failing on my PR", "explain CI failures", "what do
  the failed checks mean", or "why is CI red".
---

# pr-checks-summary capability

Interprets failed CI checks and proposes likely fixes; doesn't just list status.

## Input guards

- **Forge detection** — run `git remote get-url origin` and classify per `../../references/forge-adapters.md`. Surface `forge=<x>; capability assumes GitHub gh by default` in the proposal preamble. This capability parses GitHub Actions log shape that has no portable equivalent on other forges — refuse cleanly on non-GitHub remotes rather than producing a degraded GitHub-shaped output.
- Resolve PR (user-supplied OR `gh pr list --head <branch>`).
- `gh` auth required.
- If no checks are configured: stop with "no CI checks configured for this repo".

## Workflow

### 1. Fetch check status

Canonical machine-readable source (portable across gh versions):

```
gh pr view <num> --json statusCheckRollup
```

Or fetch run-level detail directly via REST:

```
gh api repos/{o}/{r}/commits/{headRefOid}/check-runs --paginate
```

Use `gh pr checks <num>` for human-readable output only; its `--json` flag exists only on newer gh (≥ 2.36) and isn't relied on here.

### 2. Bucket by status

`statusCheckRollup` mixes two node types. For `CheckRun` nodes switch on `status` (in-flight) then `conclusion` (terminal); for legacy `StatusContext` nodes switch on `state`:

- **PENDING** — CheckRun `status ∈ {QUEUED, IN_PROGRESS, WAITING, REQUESTED, PENDING}`; StatusContext `state ∈ {PENDING, EXPECTED}` (in-flight, or a required status context still awaited — `EXPECTED` is not a pass)
- **PASS** — CheckRun `conclusion ∈ {SUCCESS, NEUTRAL}` (NEUTRAL passes with caveats); StatusContext `state == SUCCESS`
- **FAIL** — CheckRun `conclusion ∈ {FAILURE, CANCELLED, TIMED_OUT, ACTION_REQUIRED, STARTUP_FAILURE, STALE}`; StatusContext `state ∈ {FAILURE, ERROR}`
- **SKIPPED** — CheckRun `conclusion == SKIPPED` (benign)

### 3. For each FAIL, fetch logs

```
gh run view <run-id> --log-failed
```

Or for a specific check via API:

```
gh api repos/{o}/{r}/check-runs/{check-id} --jq '.output.text, .output.summary'
```

Parse the log to extract:
- Failure type (test failure, lint error, build error, type error, deploy failure, security finding)
- Error message lines (often the last few lines of output)
- Affected files (when discoverable)

### 4. Classify and pattern-match

| Pattern | Classification | Likely fix |
|---|---|---|
| `FAILED test_*` / `× <test name>` | Test failure | Reproduce locally with the framework's filter flag |
| `error: <rule> (eslint, ruff, etc.)` | Lint | Run the formatter / linter locally; see config in `pyproject.toml` / `.eslintrc` |
| `error[E0XXX]` (Rust), `error: cannot find` (Go) | Compile error | Build locally; check imports / type mismatches |
| `error TS2XXX` (TypeScript) | Type error | Run `tsc --noEmit`; check inferred types |
| `Permission denied` / `403 Forbidden` in deploy | Deploy auth | Check `secrets` config; rotate if expired |
| `Vulnerability found` / `HIGH` / `CRITICAL` from snyk/trivy | Security scan | Update affected dependency or suppress with justification |
| `Coverage <N%` below threshold | Coverage | Add tests to changed files; check `.coveragerc` threshold |
| `dependency cycle` / `circular import` | Architecture | Refactor to break cycle |
| `OOM` / `Killed` / `signal: killed` | Resource limit | Increase runner size or split test suite |
| Timeout (`timed out after Xm`) | Slow tests / flake | Investigate flake; check for `pytest.mark.slow` or similar |
| `git checkout` failure / submodule | Workflow setup | Check workflow YAML for `fetch-depth` / `submodules: true` |
| Custom failure with `::error::` annotation | Workflow-emitted | Read the annotation message verbatim |

For patterns not in the table, surface the raw error message and mark as "uncategorized — review log".

### 5. Group related failures

Multiple failures often share a root cause:

- Same error message across 3 check matrix entries → one root cause, not three
- All test failures in one file → one bug, not many
- Lint failure + type error on same file → one PR that needs format pass

Group these and report the group root cause once with affected check names.

### 6. Output

```
PR #42 — CI failures summary (4 failed of 12 checks)

## Test failures (2 grouped)

**test (3.11)**, **test (3.12)** — 1 failing test, same on both Python versions:

  test_token_refresh_handles_expiry — AssertionError: expected None, got <Token: expired>
  src/auth/refresh.py:42

  Likely fix: the guard check returns the expired token instead of None when
  expiry is in the past. See src/auth/refresh.py:42.

  Reproduce locally:
    pytest src/auth/test_refresh.py::test_token_refresh_handles_expiry -xvs

## Lint failure (1)

**lint** — ruff rule F841 (unused variable):

  src/auth/refresh.py:38: F841 Local variable `expiry_dt` is unused

  Likely fix: `ruff check --fix src/auth/refresh.py` or remove the unused var.

## Deploy failure (1, likely transient)

**deploy-preview** — 403 Forbidden when pushing to preview env.

  Likely fix: this is usually transient or auth-rotation. Re-run with
  `gh run rerun <run-id>` first; if persistent, check `PREVIEW_DEPLOY_KEY`
  secret rotation in repo settings.

## Pending (3)

**security-scan**, **integration-test**, **build-arm64** — still running.

## Pass (5)

build-x64, build-arm, smoke-test, docs, link-check — green.
```

Always surface:
- Per-failure root cause (extracted error)
- Likely fix (when recognizable; "uncategorized" when not)
- Reproduce-locally command when applicable
- Re-run command for transient failures

## Edge cases

- **Check has no log accessible** (third-party check, GitHub App without log access) — surface what's available (status + URL); say "logs not accessible — visit <URL>".
- **Workflow uses dynamic matrix** — same job name with different parameters; differentiate by matrix axis labels.
- **Required vs optional checks** — distinguish; failing optional checks are warnings, failing required checks block merge.
- **Stale check from older SHA** — if `head_sha` of the check ≠ current `headRefOid`, mark "stale: ran on previous commit; re-run for accurate result".
- **Very long logs** — fetch tail only (last 100 lines typically captures the failure), avoid blowing token budget.

## Anti-patterns

- Don't just list `gh pr checks` output — that's already a thing. Interpret.
- Don't fabricate fix recommendations for uncategorized failures — surface the raw error and admit you don't recognize it.
- Don't run `gh run rerun` automatically — surface the command.
- Don't suggest disabling a failing check ("just remove the test") — surface the failure as something to fix.
- Don't conflate stale checks (from older SHA) with current ones — flag them separately.
- Don't load full logs for every check; only failed checks need log inspection.
