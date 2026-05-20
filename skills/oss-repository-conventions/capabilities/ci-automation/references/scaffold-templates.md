# ci-automation — scaffold templates

Workflow starting points for the `ci-automation` capability. Pin every
third-party action to a full commit SHA (resolve the SHA for the version you
want) and keep `permissions` minimal. Tailor the matrix and commands to the stack.

## CI workflow — `.github/workflows/ci.yml`

```yaml
name: CI

on:
  pull_request:
  push:
    branches: [main]

# Least privilege by default; elevate per-job only when needed.
permissions:
  contents: read

concurrency:
  group: ci-${{ github.ref }}
  cancel-in-progress: true

jobs:
  test:
    runs-on: ubuntu-latest
    timeout-minutes: 15
    strategy:
      matrix:
        version: ["<v1>", "<v2>"]   # language versions to support
    steps:
      # Pin to a commit SHA; the comment records the human-readable version.
      - uses: actions/checkout@<sha>          # v4
      - uses: <setup-action>@<sha>            # vX
        with:
          version: ${{ matrix.version }}
      - run: <install command>
      - run: <lint command>
      - run: <test command>
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
