# CI detection

Establishing whether a declared tool actually runs. This is the half of the scan that finds real defects, because a configured tool that nothing executes is invisible to everyone until the day it matters.

## The question

For each floor tool the scan found declared, answer one question: **does something in this repository cause it to run on a change?** The answer is `yes` with a citation, `no`, or `unknown` with a reason. Never guess between them.

## Where execution can live

Check these in order; stop at the first that answers definitively, but keep looking when the answer is "not here" rather than "no".

1. **Workflow files** — `.github/workflows/*.yml` **and** `*.yaml` (both are accepted, and reading only one spelling misses whole pipelines and reports their tools as unwired), `.gitlab-ci.yml`, `.circleci/config.yml`, `azure-pipelines.yml`, `Jenkinsfile`. Read the `run:` / `script:` blocks and look for the tool's invocation. A workflow that runs on `push` to a single branch and never on pull requests grades "runs, weakly" below — the tool runs, but not where review happens.
2. **Task runners** — `Makefile`, `justfile`, `Taskfile.yml`, `noxfile.py`, `tox.ini`, `package.json` scripts, `mise.toml` tasks, `cargo-make`. CI frequently calls one of these rather than the tool directly, so a workflow step reading `make lint` is an indirection to resolve, not an answer.
3. **Hook configuration** — `.pre-commit-config.yaml`, `.husky/`, `lefthook.yml`, `.githooks/`. A hook is real execution but a weaker guarantee than CI: it runs on the machines that installed it. A hook-only tool grades "runs, weakly" below, reported as running with the hook named — a contributor who never installed it is not covered, and neither is the merge.
4. **Editor and IDE config** — `.vscode/settings.json` and friends. This is _not_ execution. A formatter enabled on save in one editor's settings is a convenience for the people using that editor, and reporting it as wiring would be the most flattering possible reading of the evidence.

## Resolving indirection

A workflow step calling a task runner is answered by reading the task. `make lint` is resolved by finding the `lint` target in the `Makefile` and reading what it runs; `npm run lint` by reading `scripts.lint` in `package.json`. Follow one level of indirection at minimum, and keep following while each step resolves.

Stop and grade `unknown` when the chain leaves the repository — a step that calls a script the repo does not contain, a reusable workflow in another repository, a container image whose entrypoint is not visible here. Name what could not be resolved. "CI calls `./ci/run-checks`, which is not tracked in this repository" is a useful sentence; inferring that the linter therefore does not run is not.

## What counts as running

Grade each **invocation** first, then grade the tool by the **strongest** invocation found. A repository routinely has several — a CI job and a hook, or two workflows — and the tool's guarantee is the best of them, not the first one the scan happened to read.

Per invocation:

- **Runs**: fires on pull requests, with a failing exit status that fails the job.
- **Runs, weakly**: cannot fail a change that would break it. Either the failure is swallowed — `|| true`, `continue-on-error: true`, a step marked non-blocking — or it never fires where the change is reviewed: hook-only, schedule-only, or a trigger that excludes pull requests. A job that fires only on pushes to the default branch belongs here: it does run, and it runs after review rather than during it, so a break is caught once already merged.

Then, for the tool:

- Any invocation grading **Runs** makes the tool **Runs**, whatever else exists beside it. A proper PR job is not weakened by a hook sitting next to it.
- Otherwise, any invocation grading **Runs, weakly** makes the tool **Runs, weakly** — name which invocation and why it is weak.
- Otherwise, if some path could not be resolved, **Unknown**, naming the path. This is the last resort rather than the first: an unreadable reusable workflow beside a direct PR invocation says nothing about the direct one, and reporting the tool as unknown would discard evidence the scan already has.
- Otherwise, **Does not run**: declared in config, invoked nowhere the scan could find, after resolving indirection, with no unresolved path left to explain the absence.

The order matters in exactly one direction. Strength aggregates upward — the best invocation wins — while `unknown` only applies when nothing better is known, because it is a statement about the scan rather than about the repository.

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
