# dev-setup — scaffold templates

Reproducible-environment files for the `dev-setup` capability. Pin versions to
what the repo already uses (read existing configs / CI) before writing.

## `mise.toml` (house style toolchain pinning)

```toml
[tools]
# Pin to the versions the repo actually uses
node = "22"
python = "3.13"

[env]
# Project-scoped environment (optional)
# VIRTUAL_ENV = ".venv"

[tasks.setup]
description = "Install deps and hooks"
run = "scripts/setup"

[tasks.test]
run = "<test command>"
```

## `.env.example`

```dotenv
# Copy to .env and fill in. Never commit .env.
# Document every variable the code reads; use safe placeholders.
API_BASE_URL=https://api.example.com
# API_TOKEN=        # required: token with <scope>
LOG_LEVEL=info
```

## `scripts/setup` (one-command bootstrap)

```sh
#!/usr/bin/env sh
set -eu

# Install the pinned toolchain (mise) if available
command -v mise >/dev/null 2>&1 && mise install

# Install project + dev dependencies (tailor to the stack)
# python: pip install -e ".[dev]"   or   pip install -r requirements-dev.txt
# node:   npm ci
# go:     go mod download

# Install git hooks if the repo uses them
command -v pre-commit >/dev/null 2>&1 && pre-commit install || true

echo "Setup complete. Run the tests with: <test command>"
```

Make it executable: `chmod +x scripts/setup`, and reference it from
CONTRIBUTING and the README.
