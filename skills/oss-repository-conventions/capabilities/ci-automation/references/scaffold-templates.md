# ci-automation — hardening patterns

This capability *hardens* workflows. The base composable CI shape — the `setup`
composite action, the thin `ci.yml` caller, and the CodeQL workflow — comes from
the automation-baseline capability's building blocks; harden whatever it (or the
repo) produces using the patterns below. Pin every third-party action to a full
commit SHA.

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

First-party `actions/*` are lower risk but still better pinned. Tools like
`ratchet` or a pin-verification CI step keep this honest.

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
# per job:
    timeout-minutes: 15        # cap stuck runs
```

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
