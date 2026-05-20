# code-style — scaffold templates

Starting configs for the `code-style` capability. Pick one formatter per language; align indent/EOL with `.editorconfig`. Tailor to the repo's languages.

## `.pre-commit-config.yaml`

```yaml
repos:
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v5.0.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-merge-conflict
      - id: check-yaml
  # Python (uncomment if applicable)
  # - repo: https://github.com/astral-sh/ruff-pre-commit
  #   rev: v0.8.0
  #   hooks: [{ id: ruff, args: [--fix] }, { id: ruff-format }]
  # JS/TS (uncomment if applicable)
  # - repo: https://github.com/biomejs/pre-commit
  #   rev: v0.6.0
  #   hooks: [{ id: biome-check }]
```

Install with `pre-commit install`.

## Python — `pyproject.toml` (ruff: lint + format in one tool)

```toml
[tool.ruff]
line-length = 88
target-version = "py313"

[tool.ruff.lint]
select = ["E", "F", "I", "UP", "B"]   # pycodestyle, pyflakes, isort, pyupgrade, bugbear

[tool.ruff.format]
quote-style = "double"
```

## JS/TS — `biome.json` (lint + format in one tool)

```json
{
  "$schema": "https://biomejs.dev/schemas/1.9.4/schema.json",
  "formatter": { "enabled": true, "indentStyle": "space", "indentWidth": 2 },
  "linter": { "enabled": true, "rules": { "recommended": true } }
}
```

> If the repo already uses ESLint + Prettier, keep that pair instead of adding Biome — don't run two formatters for the same language.
