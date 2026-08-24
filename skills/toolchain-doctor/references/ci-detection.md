# CI detection

Establishing whether a declared tool actually runs. This is the half of the scan that finds real defects, because a configured tool that nothing executes is invisible to everyone until the day it matters.

## The question

For each floor tool the scan found declared, answer one question: **does something in this repository cause it to run on a change?** The answer is `yes` with a citation, `no`, or `unknown` with a reason. Never guess between them.

## Where execution can live

Check these in order; stop at the first that answers definitively, but keep looking when the answer is "not here" rather than "no".

1. **Workflow files** — `.github/workflows/*.yml`, `.gitlab-ci.yml`, `.circleci/config.yml`, `azure-pipelines.yml`, `Jenkinsfile`. Read the `run:` / `script:` blocks and look for the tool's invocation. A workflow that runs on `push` to a single branch and never on pull requests is a partial answer worth reporting as such — the tool runs, but not where review happens.
2. **Task runners** — `Makefile`, `justfile`, `Taskfile.yml`, `noxfile.py`, `tox.ini`, `package.json` scripts, `mise.toml` tasks, `cargo-make`. CI frequently calls one of these rather than the tool directly, so a workflow step reading `make lint` is an indirection to resolve, not an answer.
3. **Hook configuration** — `.pre-commit-config.yaml`, `.husky/`, `lefthook.yml`, `.githooks/`. A hook is real execution but a weaker guarantee than CI: it runs on the machines that installed it. Report a hook-only tool as running, and say that it runs only locally.
4. **Editor and IDE config** — `.vscode/settings.json` and friends. This is _not_ execution. A formatter enabled on save in one editor's settings is a convenience for the people using that editor, and reporting it as wiring would be the most flattering possible reading of the evidence.

## Resolving indirection

A workflow step calling a task runner is answered by reading the task. `make lint` is resolved by finding the `lint` target in the `Makefile` and reading what it runs; `npm run lint` by reading `scripts.lint` in `package.json`. Follow one level of indirection at minimum, and keep following while each step resolves.

Stop and grade `unknown` when the chain leaves the repository — a step that calls a script the repo does not contain, a reusable workflow in another repository, a container image whose entrypoint is not visible here. Name what could not be resolved. "CI calls `./ci/run-checks`, which is not tracked in this repository" is a useful sentence; inferring that the linter therefore does not run is not.

## What counts as running

- **Runs**: invoked by a CI job that fires on pull requests, or on the default branch, with a failing exit status that fails the job.
- **Runs, weakly**: invoked only in a hook, only on a schedule, only on one branch, or with its failure swallowed — `|| true`, `continue-on-error: true`, a step marked non-blocking. This is its own reportable state: the tool runs and cannot fail anything, which is close enough to not running that a maintainer should hear about it.
- **Does not run**: declared in config, invoked nowhere the scan could find, after resolving indirection.
- **Unknown**: the chain left the repository, or a file the chain needs could not be read.

The swallowed-failure case deserves the extra attention. A CI step that runs the linter and cannot fail looks green forever and reads, in every summary anyone glances at, exactly like a repository whose linter passes. It is the single most misleading configuration in this whole subject area, and it is easy to introduce by accident while getting a pipeline to pass.

## Reporting

Configuration and execution are reported as two columns, never merged into one verdict:

```text
| Tool | Declared in | Runs |
| --- | --- | --- |
| ruff | pyproject.toml [tool.ruff] | .github/workflows/ci.yml → make lint |
| mypy | (not declared) | — |
| shellcheck | (not declared) | .github/workflows/ci.yml (invoked directly, no config file) |
```

The last row is worth its own note: a tool invoked in CI with no configuration file is running on its defaults. That is not a gap — defaults are a legitimate choice, and shellcheck's are good — but it is a fact a maintainer should know, because nothing in the repository records what the team has agreed to.
