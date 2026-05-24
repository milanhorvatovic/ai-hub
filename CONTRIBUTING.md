# Contributing to ai-hub

Thanks for your interest! ai-hub is an incubator for AI-agnostic artifacts — skills, docs, and related content. This guide covers setup, the change process, and what we expect in a pull request.

## Getting started

1. Fork and clone the repository.
2. Create a virtualenv and install the test dependencies:

   ```sh
   python -m venv venv
   ./venv/bin/pip install -r requirements-test.txt
   ```

3. Run the test suite to confirm a clean baseline:

   ```sh
   ./venv/bin/pytest -q
   ```

## Repository layout

- `skills/<name>/` — one skill per directory: `SKILL.md` (the always-loaded router), optional `capabilities/<name>/capability.md`, and shared `references/`.
- `tests/skills/<name>/` — stdlib-only pytest structural self-tests for each skill (frontmatter, semver, capability/reference resolution).

## Making a change

- Create a topic branch from `main`.
- Keep changes focused; one logical change per pull request.
- Add or update a skill's structural tests for any change to its shape.
- Run `./venv/bin/pytest -q` before pushing. Markdown is formatted with Prettier (`proseWrap: never`) per `.prettierrc.json` — author prose as one line per paragraph and let it wrap.

## Pull requests

- Fill in the PR template; describe what changed and why, and which skill it touches.
- PRs are squash-merged — write a clear, imperative PR title (it becomes the squash commit subject).

## Contribution basis

By contributing you agree your work is licensed under the project's [MIT License](LICENSE). No CLA or sign-off is required.

## Code of conduct

This project follows its [Code of Conduct](CODE_OF_CONDUCT.md). By participating you agree to uphold it.
