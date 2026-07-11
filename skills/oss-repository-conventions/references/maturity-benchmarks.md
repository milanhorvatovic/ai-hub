# Maturity benchmarks

The rubric in `oss-health-rubric.md` is the skill's own scoring. This file maps it to **recognized external benchmarks** so a full-repo audit can report against programs maintainers and downstreams already trust — not just an internal number.

## Benchmarks to report

| Benchmark | Measures | How to read it |
| --- | --- | --- |
| **GitHub community-profile %** | presence of the standard health files | `gh api repos/{owner}/{repo}/community/profile --jq .health_percentage` |
| **OpenSSF Scorecard** | automated security-practice score (0–10) across ~18 checks | run the Scorecard action / `scorecard` CLI; the skill's audit ids carry `scorecard:` tags that map to its checks |
| **OpenSSF Best Practices Badge** | project-process maturity in three tiers | self-certification at bestpractices.dev; map findings to passing / silver / gold |
| **SLSA build level** | build / provenance integrity (L0–L3) | see the security-policy `build-provenance` check |
| **Project maturity ladder** | foundation-readiness | CNCF sandbox / incubating / graduated; Apache podling → TLP — governance + community signals |

## Best Practices Badge — tier cheatsheet

- **passing:** OSS license, public version control, version-controlled releases, a documented bug-reporting process, a working build + automated test, no known unpatched vulnerabilities, basic crypto hygiene (HTTPS, no hard-coded secrets).
- **silver:** + a contribution policy (DCO/CLA) and code of conduct, documented architecture, tests run on every change, at least two maintainers, signed releases.
- **gold:** + at least two unassociated significant contributors, a reproducible build, high test coverage gated in CI, and signed releases verified by a documented process.

The skill doesn't certify the badge; it reports which tier the current findings would satisfy and what's missing for the next.

## Using benchmarks in the full-repo audit

After the per-domain audit, emit a short **benchmark roll-up**: the GitHub community-profile %, the rubric score, the Best Practices Badge tier the repo would currently pass (and the gap to the next), and — when the repo ships artifacts — its SLSA level. Cite the source for each; never assert a Scorecard score without running Scorecard (mark it `unknown` if it wasn't run).
