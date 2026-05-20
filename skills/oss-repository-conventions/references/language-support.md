# Language support

Shared model for the language-dependent capabilities (code-style, testing-quality,
dev-setup, dependency-supply-chain, ci-automation, release-versioning, licensing
headers, repo-infrastructure `.gitignore`, automation-baseline). This file owns
the **detection method** and the **degrade principle** — the parts that are
identical everywhere. The **specific supported set is per capability**, declared
in each capability's `## Languages` section, because support is bound to the
*tool*, not the skill: Dependabot's `package-ecosystem` list, release-please's
`release-type` list, and the set of languages with a formatter are all different.

## Detect first

Identify the repo's language(s) before recommending anything, in this order:

1. **Manifests / project files** (most reliable): `pyproject.toml` / `setup.cfg` (Python), `package.json` (JS/TS), `go.mod` (Go), `Cargo.toml` (Rust), `Package.swift` / `*.xcodeproj` / `*.xcworkspace` (Swift), `*.podspec` / Objective-C sources, `Gemfile` (Ruby), `pom.xml` / `build.gradle` (Java/Kotlin), `composer.json` (PHP).
2. **GitHub Linguist** when `gh` is available: `gh api repos/{owner}/{repo}/languages` — gives the byte-share breakdown, good for ranking the primary language and spotting polyglot repos.
3. **File extensions** as a fallback: sample tracked files (`git ls-files`) and tally extensions.

Report the detected language(s) and which signal identified each.

## Support tiers (a concept each capability applies to its own set)

- **First-class** — the capability recommends concrete, named tooling and can scaffold it.
- **Recognized** — the capability names the ecosystem and gives generic guidance, but doesn't scaffold specific tool config.
- **Unknown** — the capability degrades to language-agnostic guidance and says plainly that it has no specific recommendation for this stack.

A language can sit in different tiers across capabilities (e.g. Swift is
first-class for code-style and has a Dependabot ecosystem, but release-please has
no Swift `release-type`). That's expected — each capability's `## Languages`
section is the source of truth for its own tiers.

## Degrade principle (never fabricate)

- **Never invent a tool name.** If a language isn't in a capability's supported set, do not guess a formatter/linter/test-runner/package-manager — say there's no specific recommendation and offer the language-agnostic baseline.
- Prefer the **most reliable signal**; don't over-claim a language from a single stray file.
- State the gap explicitly in the report so the maintainer knows it's unsupported, not overlooked.

## Polyglot & monorepos

- Detect **all** languages, not just the primary one.
- Audit each language independently; a finding for one language doesn't imply another.
- Expect per-package / per-directory configs in monorepos; a single root config may under-cover.
