# ai-hub

Incubator hub for AI-agnostic artifacts of every shape — skills, docs, MCP servers, conventions, integration templates, and other content that helps an agent harness do its job better. Spec-conformant where specs exist (Agent Skills, MCP). Portable across Claude Code, Codex, Cursor, Gemini CLI, and other modern agent runtimes.

## Repository layout

- `skills/<name>/` — one skill per directory: `SKILL.md` (the always-loaded router), optional `capabilities/<name>/capability.md`, and shared `references/`.
- `tests/skills/` — stdlib-only pytest suite: `test_structure_all.py` validates every skill's structure generically (frontmatter, spec limits, annotated semver, capability routing, link resolution, pointer direction); `tests/skills/<snake_name>/` (the skill name snake_cased) holds the content contracts unique to one skill.

## Skills

- **behavior-coach** — distills a stronger model's observable working behavior into a portable skill a weaker target can load.
- **coding-principles** — implementation discipline for any coding task.
- **git-toolkit** — branch/commit/PR/release narration across the git + GitHub lifecycle.
- **docs-steward** — orchestrates markdown formatters + yamllint over a repo's docs.
- **oss-repository-conventions** — scans, audits, and scaffolds an open-source repository toward and along a top-notch standard.
- **toolchain-doctor** — examines a repository's per-language tooling and prescribes the setup it is missing, without ever installing anything.

## Install

Skills install with [`npx skills`](https://github.com/vercel-labs/skills), which copies a skill into your agent's config directory.

```sh
# One skill (project scope, the default):
npx skills add https://github.com/milanhorvatovic/ai-hub/tree/main/skills/git-toolkit

# Every skill in the repo:
npx skills add milanhorvatovic/ai-hub --all

# Global scope (your user directory instead of the project): add -g
npx skills add https://github.com/milanhorvatovic/ai-hub/tree/main/skills/git-toolkit -g
```

`npx skills` installs the current `main`. Each skill also carries a SemVer in its `SKILL.md` (`metadata.version`) and is cut as a `<skill>-v<x.y.z>` tag and GitHub Release; the repository publishes dated CalVer (`vYYYY.MM.MICRO`) catalog snapshots over the set. Each skill's history lives in its own `skills/<name>/CHANGELOG.md` and GitHub Releases; the root [CHANGELOG.md](CHANGELOG.md) is the frozen pre-automation baseline. See [docs/adr/0001-release-and-versioning.md](docs/adr/0001-release-and-versioning.md) for the versioning model.

### Verifying a bundle

Each per-skill Release also attaches a reproducible zip bundle (`<skill>-<version>.zip`, containing the skill under a top-level `<skill>/` directory plus the `LICENSE`), a `SHA256SUMS` file, and sigstore build provenance. Download the bundle and `SHA256SUMS` into the same directory and run these from there — `SHA256SUMS` lists bare filenames, so `sha256sum -c` resolves them in the current directory:

```sh
# Integrity — the bytes match what was published:
sha256sum -c SHA256SUMS

# Provenance — a valid build-provenance attestation for these bytes exists in this repository:
gh attestation verify <skill>-<version>.zip --repo milanhorvatovic/ai-hub
```

Then unzip the bundle into your agent's skills directory.

## Develop

```sh
python -m venv venv
./venv/bin/pip install -r requirements-test.txt
npm ci
./venv/bin/pytest -q
```

Markdown is formatted with Prettier (`proseWrap: never`) — see `.prettierrc.json`. Python is linted with Ruff (`[tool.ruff]` in `pyproject.toml`). Both are enforced in CI on every PR: `ruff check` and `npm run format:check` each block. Prettier's version is pinned in `package-lock.json` — `npm ci` installs it, `npm run format` fixes formatting. `.pre-commit-config.yaml` wires both to run locally at commit time for contributors who want them.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) and the [Code of Conduct](CODE_OF_CONDUCT.md). Report security issues privately per the [security policy](https://github.com/milanhorvatovic/ai-hub/security/policy).

## License

[MIT](LICENSE).
