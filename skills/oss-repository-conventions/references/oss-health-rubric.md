# OSS health rubric

The scoring model behind `audit` mode. Each capability owns a slice of this
rubric; the router's full-repo audit aggregates them into one health score.

## Severity

Every check resolves to one severity. Severity is a property of the check, not
of how badly the repo wants the feature — don't inflate.

| Severity | Meaning | Examples |
|---|---|---|
| `must` | A public OSS repo is materially broken or legally unclear without it | no `LICENSE`; no `README`; secrets committed; no CI on a published package |
| `should` | Expected of a well-run project; absence is a real gap reviewers notice | no `SECURITY.md`; no `CONTRIBUTING`; no `CODE_OF_CONDUCT`; no dependency automation; unpinned third-party actions |
| `could` | Nice-to-have that raises polish or reach | `FUNDING.yml`; issue forms (vs plain templates); README badges; ADRs |

## Score

A repo's health score is the share of *applicable* checks satisfied, weighted
by severity. Inapplicable checks are excluded, not failed (a pure-docs repo has
no test framework to score).

```
weight: must = 3, should = 2, could = 1
score  = sum(weight of satisfied applicable checks)
         / sum(weight of all applicable checks)   -> 0–100%
```

Report the score per domain and rolled up. Always show the unmet `must` and
`should` items beside the number — the number alone is not actionable. Mirror
GitHub's own community-profile health percentage when it is available
(`gh api repos/{owner}/{repo}/community/profile --jq .health_percentage`), and
note where this rubric is stricter than GitHub's (GitHub does not score CI,
signing, dependency automation, or supply-chain).

## Applicability gates

Skip a check (don't fail it) when:

- the repo is private and the check only matters for public projects (e.g. `FUNDING.yml`);
- the domain doesn't exist here (no source → skip code-style/testing; no published artifact → relax release/signing to `could`);
- the repo declares the convention deliberately-absent in an agent-instruction file or `CONTRIBUTING.md` (honor the declaration, note it).

## Cross-domain `must` baseline

The minimum a public OSS repo needs before any domain polish matters:

1. `LICENSE` present and SPDX-identifiable — see the `licensing` capability.
2. `README` that states what the project is, how to install, and how to use it.
3. No secrets in history; a way to report vulnerabilities privately — see `security-policy`.
4. CI that builds and tests on PRs, if the repo ships code.

Per-domain checks live in each capability under its `## Audit checks` section,
each tagged with one of the severities above so the aggregator can weight them.
