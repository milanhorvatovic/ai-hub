# ai-hub

Incubator hub for AI-agnostic artifacts of every shape — skills, docs, MCP servers, conventions, integration templates, and other content that helps an agent harness do its job better. Spec-conformant where specs exist (Agent Skills, MCP). Portable across Claude Code, Codex, Cursor, Gemini CLI, and other modern agent runtimes.

## Repository layout

- `skills/<name>/` — one skill per directory: `SKILL.md` (the always-loaded router), optional `capabilities/<name>/capability.md`, and shared `references/`.
- `tests/skills/<name>/` — stdlib-only pytest structural self-tests for each skill (frontmatter, semver, capability/reference resolution).

## Skills

- **coding-principles** — implementation discipline for any coding task.
- **git-toolkit** — branch/commit/PR/release narration across the git + GitHub lifecycle.
- **docs-steward** — orchestrates markdown formatters + yamllint over a repo's docs.
- **oss-repository-conventions** — scans, audits, and scaffolds an open-source repository toward and along a top-notch standard.

## Develop

```sh
python -m venv venv
./venv/bin/pip install -r requirements-test.txt
./venv/bin/pytest -q
```

Markdown is formatted with Prettier (`proseWrap: never`) — see `.prettierrc.json`. Python is linted with Ruff (`[tool.ruff]` in `pyproject.toml`), enforced in CI on every PR; `.pre-commit-config.yaml` wires Ruff and Prettier for contributors who want them locally.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) and the [Code of Conduct](CODE_OF_CONDUCT.md). Report security issues privately per [SECURITY.md](.github/SECURITY.md).

## License

[MIT](LICENSE).
