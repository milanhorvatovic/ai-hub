# ci-automation — scaffold templates

This capability _hardens_ workflows. The base composable CI shape — the `setup` composite action, the thin `ci.yml` caller, and the CodeQL workflow — comes from the automation-baseline capability's building blocks; harden whatever it (or the repo) produces using the patterns below. Pin every third-party action to a full commit SHA.

## Least-privilege permissions

Default the whole workflow to read-only; elevate only the jobs that need more.

```yaml
permissions:
  contents: read          # workflow-wide default

jobs:
  release:
    permissions:          # elevate only this job
      contents: write
      id-token: write     # OIDC, instead of a long-lived secret
```

## SHA-pinning third-party actions

```yaml
# Pin to a full commit SHA; the trailing comment records the human version.
- uses: actions/checkout@<40-char-sha>          # v4
- uses: ossf/scorecard-action@<40-char-sha>     # v2
```

First-party `actions/*` are lower risk but still better pinned. Tools like `ratchet` or a pin-verification CI step keep this honest.

## OIDC for deploy/publish (no long-lived secrets)

```yaml
  publish:
    permissions:
      id-token: write
    steps:
      - uses: <cloud-login-action>@<sha>   # exchanges the OIDC token for short-lived creds
```

## Concurrency and timeouts

```yaml
concurrency:
  group: ${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: true   # cancel superseded runs
# and on every runner-backed job (a `uses:` caller can't declare one — cap
# inside the called workflow):
#   timeout-minutes: 15      # cap stuck runs
```

## Fork-PR safety (the "pwn request" guard)

Untrusted code from a fork must never run with secrets or write scope. Prefer `pull_request` (no secrets, read-only token); reach for `pull_request_target` only when you must, and never check out the PR head under it. Gate any secret-bearing or write job on the head being in-repo.

```yaml
on:
  pull_request:            # fork code runs WITHOUT secrets, token defaults read-only
    types: [opened, synchronize, reopened]

jobs:
  privileged:
    # Refuse fork PRs for any job that touches secrets or needs write scope.
    if: github.event.pull_request.head.repo.full_name == github.repository
    permissions:
      pull-requests: write
    steps:
      - uses: actions/checkout@<sha>            # v4
        with:
          ref: ${{ github.event.pull_request.head.sha }}
          persist-credentials: false           # don't leave the token on disk
```

Anti-pattern: `on: pull_request_target` + `actions/checkout` of `head.ref` + a `run:` step — that executes fork code in a context that holds your secrets.

## Artifact / invariant verification gate

When the repo commits a generated artifact (a bundled `dist/`, generated clients/docs) or pins actions/lockfiles, make CI _enforce_ the invariant, not just lint it — rebuild and fail on drift.

```yaml
  verify-dist:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@<sha>            # v4
      - uses: ./.github/actions/setup
      - run: npm run build                      # regenerate the artifact
      - name: Fail if the committed artifact is stale
        run: git diff --exit-code -- dist/      # red when dist/ doesn't match source
```

The autonomous-update rebuild step (dependency-supply-chain) relies on this gate to catch a missed or wrong rebuild.

## OpenSSF Scorecard — `.github/workflows/scorecard.yml` (optional)

```yaml
name: Scorecard

on:
  branch_protection_rule:
  schedule:
    - cron: "0 6 * * 1"
  push:
    branches: [main]

permissions: read-all

jobs:
  analysis:
    runs-on: ubuntu-latest
    permissions:
      security-events: write
      id-token: write
    steps:
      - uses: actions/checkout@<sha>            # v4
      - uses: ossf/scorecard-action@<sha>       # v2
        with:
          results_file: results.sarif
          results_format: sarif
      - uses: github/codeql-action/upload-sarif@<sha>   # v3
        with:
          sarif_file: results.sarif
```
