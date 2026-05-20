# governance — scaffold templates

Small ownership/governance files for the `governance` capability. Fill from the
repo's real structure and confirmed people before writing; never write invented
handles.

## CODEOWNERS

Goes at `.github/CODEOWNERS`. Order matters — the last matching pattern wins.

```text
# Default owners for everything in the repo
*                       @org/maintainers

# Area owners
/src/api/               @org/api-team
/docs/                  @org/docs
/.github/workflows/     @org/release
```

## MAINTAINERS.md

```markdown
# Maintainers

| Maintainer | Area | Contact |
|---|---|---|
| @handle | <area or "all"> | <email or @handle> |

Maintainers are responsible for review, releases, and triage. To propose adding
or removing a maintainer, open an issue and follow GOVERNANCE.md.
```

## GOVERNANCE.md

```markdown
# Governance

## Roles
- **Contributors** — anyone who submits issues or pull requests.
- **Maintainers** — listed in MAINTAINERS.md; merge rights and release duties.

## Decisions
<Pick one and delete the rest:>
- **BDFL:** <name> has final say; maintainers advise.
- **Maintainer consensus:** changes merge with approval from N maintainers and no
  outstanding objections.
- **Council:** maintainers vote; simple majority decides; ties go to <tiebreak>.

## Becoming a maintainer
Sustained, high-quality contributions over <period> may lead to an invitation,
proposed by an existing maintainer and confirmed per the decision process above.
```
