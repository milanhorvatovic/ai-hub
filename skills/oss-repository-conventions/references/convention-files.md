# Catalog of convention-declaring files

The full inventory of file paths the scanner checks. Add to this list when you encounter new source files in real repos.

## Agent / contributor instructions

- `CLAUDE.md` (any case, repo root)
- `AGENTS.md` (any case, repo root)
- `.github/copilot-instructions.md`
- `CONTRIBUTING.md`, `CONTRIBUTING.rst`, `CONTRIBUTING.txt`
- `docs/CONTRIBUTING.md`
- `.github/CONTRIBUTING.md`

## Commit format

- `.commitlintrc`, `.commitlintrc.js`, `.commitlintrc.cjs`, `.commitlintrc.json`, `.commitlintrc.yml`, `.commitlintrc.yaml`
- `commitlint.config.js`, `commitlint.config.cjs`, `commitlint.config.ts`, `commitlint.config.mjs`
- `.czrc`, `.cz.json`, `cz-config.js`, `.cz-config.js`
- `.gitlint`
- `.gitmessage`, `.gitmessage.txt` (also `git config --get commit.template`)
- `commitizen.toml`
- `package.json` (look for `config.commitizen`, `husky.hooks.commit-msg`)
- `pyproject.toml` (look for `[tool.commitizen]`)

## PR / issue templates

- `.github/PULL_REQUEST_TEMPLATE.md`
- `.github/pull_request_template.md` (lowercase variant)
- `PULL_REQUEST_TEMPLATE.md` (repo root)
- `pull_request_template.md` (repo root, lowercase)
- `docs/PULL_REQUEST_TEMPLATE.md`
- `docs/pull_request_template.md`
- `.github/PULL_REQUEST_TEMPLATE/*.md` (multi-template directory)
- `.github/ISSUE_TEMPLATE/*.md`
- `.github/ISSUE_TEMPLATE/config.yml`
- `.github/CODEOWNERS`, `CODEOWNERS`, `docs/CODEOWNERS`

## Code style

### Language-agnostic

- `.editorconfig`
- `.pre-commit-config.yaml`, `.pre-commit-config.yml`
- `.lefthook.yml`, `lefthook.yml`
- `.husky/` (directory of hook scripts)

### JavaScript / TypeScript

- `.prettierrc`, `.prettierrc.js`, `.prettierrc.json`, `.prettierrc.yml`, `prettier.config.js`, `prettier.config.cjs`
- `.eslintrc`, `.eslintrc.js`, `.eslintrc.json`, `.eslintrc.yml`, `eslint.config.js`, `eslint.config.mjs`
- `.stylelintrc*`, `stylelint.config.*`
- `tsconfig.json`, `tsconfig.base.json`, `jsconfig.json`
- `biome.json`, `biome.jsonc`
- `package.json` (look for `lint`, `format`, `prettier`, `eslintConfig` keys)

### Python

- `pyproject.toml` (look for `[tool.ruff]`, `[tool.black]`, `[tool.isort]`, `[tool.mypy]`, `[tool.flake8]`)
- `.flake8`
- `.ruff.toml`, `ruff.toml`
- `setup.cfg` (look for `[flake8]`, `[isort]`, `[mypy]`)
- `tox.ini`
- `mypy.ini`, `.mypy.ini`
- `.bandit`, `bandit.yaml`
- `.pylintrc`, `pylintrc`

### Go

- `.golangci.yml`, `.golangci.yaml`, `.golangci.toml`
- `.goimportsignore`
- `gofmt.sh` (custom format scripts)

### Rust

- `rustfmt.toml`, `.rustfmt.toml`
- `.clippy.toml`, `clippy.toml`
- `Cargo.toml` (look for `[lints]`)

### Other languages

- `swiftlint.yml`, `.swiftlint.yml`, `.swift-format`
- `.scalafmt.conf`
- `.dartlintrc`, `analysis_options.yaml` (Dart)
- `.rubocop.yml`, `.rubocop_todo.yml`
- `.kotlinter.json`
- `.shellcheckrc`

## Tests

### Python

- `pytest.ini`, `pyproject.toml` (`[tool.pytest.ini_options]`)
- `tox.ini` (`[testenv]` sections)
- `conftest.py` (test infrastructure, root or per-dir)
- `.coveragerc`, `pyproject.toml` (`[tool.coverage]`)

### JavaScript / TypeScript

- `jest.config.js`, `jest.config.ts`, `jest.config.cjs`, `jest.config.mjs`, `jest.config.json`
- `vitest.config.js`, `vitest.config.ts`
- `playwright.config.js`, `playwright.config.ts`
- `cypress.config.js`, `cypress.config.ts`, `cypress.json`
- `karma.conf.js`
- `package.json` (look for `jest`, `scripts.test`)

### Go

- `*_test.go` patterns
- `.testdata/` directories

### Other

- `phpunit.xml`, `phpunit.xml.dist`
- `RSpec`, `.rspec`
- `spec.opts`

## CI/CD

- `.github/workflows/*.yml`, `.github/workflows/*.yaml`
- `.github/actions/*/action.yml` (custom local actions)
- `.gitlab-ci.yml`
- `.circleci/config.yml`
- `Jenkinsfile`, `Jenkinsfile.*`
- `azure-pipelines.yml`, `.azure-pipelines.yml`
- `bitbucket-pipelines.yml`
- `.buildkite/pipeline.yml`
- `.drone.yml`
- `.travis.yml`
- `appveyor.yml`, `.appveyor.yml`
- `.github/dependabot.yml`, `.github/renovate.json`, `renovate.json`

## Releases

- `CHANGELOG.md`, `CHANGELOG.rst`, `CHANGELOG.txt`, `CHANGES.md`, `HISTORY.md`, `NEWS.md`
- `release-please-config.json`, `.release-please-manifest.json`
- `.releaserc`, `.releaserc.json`, `.releaserc.yml`, `release.config.js` (semantic-release)
- `changelog.yaml`, `changelog.toml` (custom mappings)
- `RELEASE.md`, `RELEASING.md`
- `.github/release.yml` (GitHub's auto-generated release notes config)
- `VERSION`, `version.txt`, `__version__.py`
- `package.json` (`version`, `release` scripts)
- `pyproject.toml` (`[project] version`, `[tool.poetry] version`)
- `Cargo.toml` (`[package] version`)

## Security

- `SECURITY.md`, `.github/SECURITY.md`, `docs/SECURITY.md`
- `.github/dependabot.yml`
- `.gitleaks.toml`, `.gitleaks.yml`
- `.trufflehog`
- `.snyk`
- `.checkov.yml`, `.checkov.yaml`
- `.semgrep.yml`, `semgrep.yml`

## Documentation

- `README.md`, `README.rst`, `README.txt`
- `docs/`, `documentation/`, `site/`
- `mkdocs.yml`, `mkdocs.yaml`
- `_config.yml` (Jekyll)
- `book.toml` (mdBook)
- `docusaurus.config.js`

## License

- `LICENSE`, `LICENSE.md`, `LICENSE.txt`
- `LICENSE-MIT`, `LICENSE-APACHE` (dual-license repos)
- `COPYING`, `COPYING.md`
- `pyproject.toml` (`[project] license`)
- `package.json` (`license`)
- `Cargo.toml` (`[package] license`)

## Localization / i18n

- `.crowdin.yml`, `crowdin.yml`
- `transifex.config`, `.tx/config`

## Misc

- `.gitignore` (patterns hint at what's expected in the repo)
- `.gitattributes` (line-ending, merge-driver, language-detection rules)
- `.mailmap` (commit-author normalization)
- `funding.yml`, `.github/FUNDING.yml`

## Adding to this catalog

When you find a convention-declaring file not listed here in a real repo, add it. Group by domain. Include the file's role in one line if it's not obvious from the name.
