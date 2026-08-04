# security-policy — scaffold templates

Template for the `security-policy` capability's scaffold mode. Tailor the reporting channel to what the repo actually offers and fill the supported-versions table from real releases — don't guess. House style places the file at `.github/SECURITY.md`. The branch-protection payload is not templated here — it ships raw as `branch-protection.example.json`, copyable as-is.

## Security policy — `SECURITY.md`

```markdown
# Security Policy

## Supported versions

| Version         | Supported |
| --------------- | --------- |
| `x.y` (latest)  | ✅        |
| `< x.y` (older) | ❌        |

## Reporting a vulnerability

Please report vulnerabilities **privately** through the channel this project offers (keep the one you use): GitHub private vulnerability reporting (the repo's **Security → Report a vulnerability** tab), email to `security@EXAMPLE`, or a private GitHub Security Advisory.

Do **not** open a public issue for security problems.

We aim to acknowledge within <N> business days and to provide a fix or mitigation timeline after triage. Coordinated disclosure is appreciated, and we are happy to credit reporters who wish to be named.
```
