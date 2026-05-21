# automation-baseline — composable building blocks

The bare-minimum, composable CI baseline. Each unit is small and reusable; the caller wires them. Pin every third-party action to a commit SHA and keep `permissions` minimal (the ci-automation capability owns hardening). Tailor commands to the stack.

## 1. `setup` composite action — `.github/actions/setup/action.yml`

One place to pin the toolchain and install dependencies, reused by every job.

```yaml
name: Setup
description: Install the pinned toolchain and project dependencies
runs:
  using: composite
  steps:
    # Tools come from mise.toml / .tool-versions (dev-setup capability)
    - uses: jdx/mise-action@<sha>          # vX
    - run: <install command>               # e.g. npm ci  |  pip install -e ".[dev]"
      shell: bash
```

> A composite action runs _after_ the caller's `checkout`, so checkout stays in the job, not here.

## 2. Thin caller — `.github/workflows/ci.yml`

No logic of its own; just wires independent, parallel jobs.

```yaml
name: CI

on:
  pull_request:
  push:
    branches: [main]

permissions:
  contents: read

concurrency:
  group: ci-${{ github.ref }}
  cancel-in-progress: true

jobs:
  static:
    runs-on: ubuntu-latest
    timeout-minutes: 10
    steps:
      - uses: actions/checkout@<sha>       # v4
      - uses: ./.github/actions/setup
      - run: <lint command>
      - run: <typecheck command>

  test:
    runs-on: ubuntu-latest
    timeout-minutes: 15
    strategy:
      matrix:
        version: ["<v1>", "<v2>"]
    steps:
      - uses: actions/checkout@<sha>       # v4
      - uses: ./.github/actions/setup
      - run: <test command with coverage>
      - uses: actions/upload-artifact@<sha>   # v4   (coverage artifact, optional)
        with: { name: coverage, path: coverage/ }
```

`static` and `test` fail independently and run in parallel — a lint error no longer hides a test failure, and vice versa. Coverage upload/badge is a separate optional concern (see the testing-quality capability).

## 3. CodeQL code scanning — `.github/workflows/codeql.yml`

Free SAST for public repositories; the baseline security scan.

```yaml
name: CodeQL

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]
  schedule:
    - cron: "0 6 * * 1"

permissions:
  contents: read
  security-events: write

jobs:
  analyze:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        language: ["<language>"]   # javascript-typescript, python, go, …
    steps:
      - uses: actions/checkout@<sha>                  # v4
      - uses: github/codeql-action/init@<sha>         # v3
        with: { languages: ${{ matrix.language }} }
      # autobuild works for interpreted langs (Python/JS/Ruby). For compiled
      # langs (Swift/Go/Rust/Java/C/C++) it often fails — replace with the
      # project's real build commands.
      - uses: github/codeql-action/autobuild@<sha>    # v3
      - uses: github/codeql-action/analyze@<sha>      # v3
```

## Scaling up: reusable workflows

When several repos share these blocks, promote them to reusable workflows and call them, so a fix lands in one place:

```yaml
# caller ci.yml in each repo
jobs:
  ci:
    uses: <org>/.github/.github/workflows/_ci.yml@<sha>
    with:
      test-command: "<test command>"
```
