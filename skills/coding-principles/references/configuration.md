# Configuration — industry conventions

Language-agnostic practices for application configuration and feature flags. Load when the code under change reads config, env vars, secrets, or feature flags. Generalizes the 12-factor CLI discipline (stated in full in the bash capability's best-practices reference) to all languages and to long-running services.

The [Twelve-Factor App](https://12factor.net/config) is the canonical reference for config-as-environment.

> **The per-language library names below were last checked 2026-08.** The precedence and validation rules do not decay; the libraries do. How to read a stamped file is stated once under "Currency" in `../SKILL.md`.

## Config sources and precedence

Configuration comes from multiple sources; resolve them in a defined order, later overriding earlier:

```
built-in defaults  <  config file  <  environment variables  <  command-line flags
```

- **Defaults** in code — sensible values so the app runs with zero config in dev.
- **Config file** (`.toml` / `.yaml` / `.json`) for structured, non-secret, environment-shared settings.
- **Environment variables** for per-deployment values and secrets (12-factor: config lives in the environment).
- **Flags** for per-invocation overrides (mostly CLIs).

## Validate at startup, fail fast

- **Parse config into a typed object at startup**, at the boundary (principle 19) — not scattered `os.environ["X"]` reads throughout the code (principle 16, explicit-over-implicit).
- **Validate eagerly**: missing required values, malformed URLs, out-of-range numbers, unparseable durations — fail at boot with a clear message, not at 3am on the first request that touches the bad value (fail-fast mantra).
- **One typed config object**, passed down from the entry point (the imperative shell). Business code receives `config.database_url`, not a call to read the environment.

```
# anti-pattern: env read deep in the call stack, no validation, fails late
def connect():
    return Database(os.environ["DATABASE_URL"])   # KeyError at first use

# convention: parse + validate once at the edge, pass the typed value down
class Config(BaseSettings):
    database_url: PostgresDsn
    request_timeout_s: float = 5.0

config = Config()              # validates at startup; clear error if invalid
db = Database(config.database_url)
```

## Secrets

- **Never commit secrets** (principle 13) — no API keys, passwords, tokens, connection strings with credentials in the repo, in config files, or in the image.
- **Inject at the boundary** — from environment, a secret manager (Vault, AWS Secrets Manager, GCP Secret Manager, sealed secrets), or a mounted file. Read once at startup; pass down.
- **Separate secret from non-secret config** — non-secret settings can live in a checked-in file; secrets come from the environment/manager only.
- **Don't log resolved config** without redacting secret fields (principle 13). Log that config loaded and which non-secret values are set, not their secret contents.

## Environment parity

- **Same config mechanism across environments** — dev, staging, prod differ only in _values_, not in _how_ config is read. Don't have a special dev code path that reads a file while prod reads env; that's where "works in dev" bugs hide.
- **No environment names in business logic** — `if env == "prod"` branches scatter and rot. Drive behavior off specific config flags (`enable_x: bool`), not off a global environment name.

## Feature flags

The code-level discipline (the flag _platform_ — LaunchDarkly, Unleash, etc. — is ops; reading a flag is code):

- **A flag is a typed config value** read at the boundary, not a magic string checked deep in the stack.
- **Flags are temporary by default.** A release flag (gating a rollout) should be removed once the feature is fully shipped. Track flag age; stale flags are debt (dead-code adjacent — principle 20).
- **Distinguish flag kinds**: short-lived _release_ flags (delete after rollout), long-lived _operational_ flags (kill switches, kept deliberately), _permission_ flags (entitlements, effectively config). Don't let release flags become permanent.
- **Default safe.** If the flag service is unreachable, fall back to a safe default (usually "off" for a new feature) — don't fail the request because a flag couldn't be read (resilience: graceful degradation).
- **Avoid flag combinatorics.** N independent boolean flags = 2^N code paths, most untested. Keep the number small; remove flags promptly.

## Principle alignment

- **Boundary parsing** (principle 19): config is untrusted input from the environment — parse and validate it into a typed object at the edge.
- **Fail fast, fail loud** (mantra): validate at startup; a misconfigured app should refuse to boot, not misbehave at runtime.
- **Explicit over implicit** + **inject external state** (principle 16): pass the resolved config object down; don't read env vars from deep in the call stack.
- **No dead code** (principle 20): retire release flags once shipped; stale flags are config debt.

## Per-language pointers

- **Python**: `pydantic-settings` (typed, validated, env + file). Avoid scattered `os.environ`.
- **TypeScript/Node**: parse `process.env` through a `zod` schema at startup into a typed config object; `convict` or `znv` for layered config.
- **Rust**: `figment` or `config` crate layered with `serde`-deserialized typed structs; validate on load.
- **Bash**: env vars with `${VAR:?error message}` to fail fast on missing required config (the bash capability's best-practices reference carries the 12-factor CLI discipline in full).
