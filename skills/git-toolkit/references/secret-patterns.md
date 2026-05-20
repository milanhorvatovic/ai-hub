# Secret-pattern catalog for pre-publication redaction

Load this whenever a capability is about to display or write text that will become a commit message or PR body. Run every pattern; on match, redact the surrounding context with `[REDACTED: <pattern_name>]` and surface a `WARN: potential secret in proposal — <pattern_name> at line N` line above the proposal.

## Pattern catalog

Listed rather than tabulated on purpose: alternation pipes (`|`) must stay literal in the raw source. A markdown table would force `\|` escaping, and a reader that consumes the raw file (not the rendered HTML) would treat `\|` as a literal pipe — breaking the alternation in engines like Python `re`. Each entry is `name` — `regex` — what it catches.

- `github_token` — `(?:gh[pousr]_[A-Za-z0-9]{36,}|github_pat_[A-Za-z0-9_]{82})` — GitHub PAT (`ghp_`), OAuth (`gho_`), user-server (`ghu_`), server-server (`ghs_`), refresh (`ghr_`), fine-grained PAT (`github_pat_`)
- `aws_access_key` — `AKIA[0-9A-Z]{16}` — AWS access key IDs
- `aws_secret_key` — `(?i)aws[_-]?secret[_-]?access[_-]?key["'\s:=]+[A-Za-z0-9/+=]{40}` — AWS secret access keys (heuristic — full keys are unconstrained chars but typically near labelled context)
- `slack_token` — `xox[bpoars]-[A-Za-z0-9-]+` — Slack bot/user/OAuth/app/refresh/scim tokens
- `google_api_key` — `AIza[0-9A-Za-z\-_]{35}` — Google API keys
- `stripe_key` — `(?:sk|rk|pk)_(?:live|test)_[A-Za-z0-9]{24,}` — Stripe secret / restricted / publishable keys
- `private_key` — `-----BEGIN[ A-Z]* PRIVATE KEY-----` — PEM-encoded RSA / EC / OpenSSH / PGP private keys
- `jwt` — `eyJ[A-Za-z0-9_-]+\.eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+` — JWTs (header.payload.signature). Often non-sensitive (public tokens) but worth flagging — frequently embed user IDs and scopes.
- `connection_string` — `(?:postgres(?:ql)?|mysql|mongodb(?:\+srv)?|redis|amqp(?:s)?)://[^/\s]*:[^@\s]+@` — Database/queue connection strings with embedded credentials
- `bearer_token` — `(?i)(?:authorization|auth)["':\s=]+bearer\s+[A-Za-z0-9._\-+/=]{20,}` — HTTP Authorization headers with bearer tokens
- `azure_storage` — `DefaultEndpointsProtocol=https;AccountName=[^;]+;AccountKey=[A-Za-z0-9+/=]{88}` — Azure Storage connection strings
- `npm_token` — `npm_[A-Za-z0-9]{36}` — npm publish tokens
- `pypi_token` — `pypi-AgEIcHlwaS5vcmc[A-Za-z0-9_-]{50,}` — PyPI API tokens

## Generic high-entropy candidates

After the named patterns, also flag:

- Base64 strings ≥ 40 chars with Shannon entropy ≥ 4.5 bits/char
- Hex strings ≥ 40 chars with entropy ≥ 3.5 bits/char (lower because hex alphabet is smaller)

These have high false-positive rates (hashes, IDs, build artifacts, content checksums). Surface as `WARN: high-entropy string — verify if secret` rather than auto-redacting. Ask the user before stripping if uncertain.

## What NOT to flag

- Public values that look like tokens but aren't: GitHub commit SHAs (always 40-char hex), npm package versions, content-addressable hashes, build IDs, Docker image digests.
- Test fixtures explicitly marked as fake: strings under `tests/`, `fixtures/`, `mocks/`, paths with `example` / `dummy` / `fake` / `test`. Flag with lower severity (`INFO: test-fixture token`) so the user can confirm.
- Git tags / branch names that contain hex.

## Action on a match

1. Redact the matched span and ~20 chars of surrounding context with `[REDACTED: <pattern_name>]`.
2. Add a `WARN: potential secret in proposal — <pattern_name> at line N` line to the verdict's notes.
3. Do not include the redacted text in the proposed body or commit message — better to drop the entire bullet/sentence than to ship a redacted-but-leaky text.
4. If multiple patterns matched, list each separately so the user can verify per-pattern.

Never decide on the user's behalf that a flagged value is safe. Always surface, even when the heuristic over-flags.

## Scope

Apply this scan to:

- Proposed commit messages (subject + body) before display.
- Proposed PR descriptions before display.
- Carry-forward content from an existing body when rewriting (the existing body may contain leaked secrets from earlier; the rewrite is the moment to redact, not re-leak).

Do NOT scan:

- Diff content the user is reading for context — that's their existing code, not new text being authored.
- Files under `.gitignore` patterns that suggest secret storage (`.env`, `secrets/`, etc.) — those shouldn't be in commit messages anyway; if they are, that's a separate problem.
