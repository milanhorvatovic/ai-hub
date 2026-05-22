---
name: licensing
description: >
  Scans, audits, and scaffolds a repository's licensing — the LICENSE file and
  its SPDX identity, dual/multi-licensing, per-file SPDX headers, REUSE
  compliance, NOTICE/attribution files, and license compatibility with declared
  dependencies. In audit mode it flags a missing or ambiguous license as a must
  and explains the legal consequence; in scaffold mode it writes a chosen
  license and (on request) adds SPDX headers. Triggers on "what license is
  this", "add a license", "is my license clear", "are my deps license-
  compatible", or a full-repo audit.
allowed-tools: Bash Read Grep Glob Write Edit
---

# licensing capability

Governs the legal clarity of the repository: is there a license, is it machine-identifiable, and is it consistent with the code and its dependencies. Reads and judges by default; writes only in scaffold mode, one file at a time.

## Modes

- **scan** — report the license(s) present and how they're declared.
- **audit** — judge clarity and compatibility against `../../references/oss-health-rubric.md`.
- **scaffold** — write a `LICENSE` (and optionally SPDX headers / `NOTICE`) after confirmation.

## Inputs & guards

- Not a git repo → stop: "not a git repository; nothing to scan."
- Already has a clear, SPDX-identifiable `LICENSE` and the user asked to scan/audit → report it as solid; don't propose changes unless asked.
- User asks to scaffold but a `LICENSE` already exists → show the existing one and require explicit confirmation to replace; never overwrite silently.
- User asks "which license should I use" without choosing → present options (see Scaffold) and ask; do not pick a license for them unilaterally.

## Languages

Detect per `../../references/language-support.md`. The `LICENSE` file and SPDX metadata are language-agnostic; only per-file SPDX _headers_ are language-bound:

- **First-class (header comment syntax):** `//` for C / C++ / Go / Rust / Java / TS / JS / Swift; `#` for Python / Ruby / Shell / YAML; `<!-- -->` for HTML / XML / Markdown.
- **Recognized:** other comment styles — add the header in the language's comment syntax when known.
- **Unknown:** skip per-file headers (the root `LICENSE` still applies); never guess a comment syntax.

## Scan

Check, in order, citing each source (catalog: `../../references/convention-files.md`, License section):

1. Root license files: `LICENSE`, `LICENSE.md`, `LICENSE.txt`, `COPYING`, dual variants `LICENSE-MIT` / `LICENSE-APACHE`.
2. Declared SPDX in package metadata: `package.json` (`license`), `pyproject.toml` (`[project] license`), `Cargo.toml` (`[package] license`), `*.gemspec`, `composer.json`.
3. Per-file SPDX headers: `grep -rl "SPDX-License-Identifier:" .` — sample, report coverage.
4. REUSE: `REUSE.toml` / `.reuse/dep5`, and a `LICENSES/` directory of SPDX texts.
5. `NOTICE` / `AUTHORS` / `COPYRIGHT` attribution files.

Identify the SPDX id of the root license by matching its text/title (MIT, Apache-2.0, BSD-3-Clause, GPL-3.0-or-later, MPL-2.0, etc.). Report `unknown / custom` if it doesn't match a standard text.

## Audit

Checks follow the schema in `../../references/oss-health-rubric.md` (`id` — **severity** [· scorecard: Name]. criterion. why):

- `license-present` — **must** · scorecard: License. Fail when no SPDX-identifiable `LICENSE` sits at repo root. A public repo with no license is "all rights reserved" — nobody may legally reuse it.
- `license-spdx-identifiable` — **must**. Warn when the license text doesn't match a known SPDX id (custom or hand-edited). Tooling and downstreams can't detect a non-standard license.
- `metadata-matches-license` — **should**. Fail when the `license` field in `package.json` / `pyproject.toml` / `Cargo.toml` differs from the `LICENSE` file's SPDX id; cite both sources. Mismatched metadata misleads package registries.
- `dependency-compatibility` — **should** (when a manifest/lockfile exists). Fail when a declared dependency's license is incompatible with the repo's (e.g. a GPL-3.0 dep in an Apache-2.0 library); warn when any dependency license is unknown. Incompatible deps make the stated license unenforceable.
- `copyright-current` — **could**. Warn when the copyright line lacks a holder or a sensible year/range. Stale copyright reads as unmaintained.
- `reuse-headers` — **could**. Pass when source files carry `SPDX-License-Identifier` headers or the repo is REUSE-compliant. Per-file clarity for downstream reuse; flag only when the repo aims for it.

## Scaffold

Only after the user has chosen a license (or confirmed the house default from `../../references/house-style.md`). Show the content, then write on confirmation.

Choosing — present the trade-off, don't decide unprompted:

| Goal | Common choice |
| --- | --- |
| Maximum adoption, minimal obligation | MIT or BSD-3-Clause |
| Permissive + explicit patent grant | Apache-2.0 |
| Library copyleft (changes to the lib stay open) | MPL-2.0 or LGPL-3.0 |
| Strong copyleft (whole work stays open) | GPL-3.0-or-later / AGPL-3.0 |

Then:

1. Fetch canonical text — prefer `gh api /licenses/{spdx} --jq .body` (authoritative, fills the copyright placeholder), or use the SPDX-listed text. Never hand-edit license bodies beyond the `[year]` / `[fullname]` placeholders.
2. Write to `LICENSE` at repo root (house style: root, plain `LICENSE`).
3. Sync metadata: update the `license` field in `package.json` / `pyproject.toml` / `Cargo.toml` to the same SPDX id (Edit, shown first).
4. Optional on request: add `SPDX-License-Identifier: <id>` headers to source files (snippet: `references/scaffold-snippets.md`), and/or set up REUSE with a `LICENSES/` dir.
5. Dual-licensing: write `LICENSE-MIT` + `LICENSE-APACHE` and add the "either at your option" notice from `references/scaffold-snippets.md` to `README`.

One confirmation per file. For an existing `LICENSE`, show a diff before replacing.

## Output

Report per `../../references/output-format.md`: scan emits the license inventory with sources; audit emits severity-tagged findings, the domain score, and a `scaffold` offer for each unmet `must` / `should`.

## Edge cases

- **Fork** — license is inherited from upstream; changing it usually isn't permitted. Flag rather than scaffold.
- **Relicensing an existing project** — requires consent of past contributors; never present as a simple file write. Surface the obligation and stop.
- **Mixed licenses across subdirectories** (monorepo) — report per-path; don't assume the root license covers vendored or differently-licensed subtrees.
- **`LICENSE` present but empty / placeholder** — treat as missing (`must`).

## Anti-patterns

- Don't pick a license for the user — present options, let them choose.
- Don't write or overwrite `LICENSE` without confirmation and (for existing files) a diff.
- Don't claim dependency compatibility when some dependency licenses are unknown — say so.
- Don't edit the body of a standard license; only fill the year/holder placeholders.
