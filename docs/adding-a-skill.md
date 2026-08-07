# Adding a skill

A new skill touches a handful of wiring points beyond its own directory. This runbook lists every step, the shape each file must have, and the check that catches a miss — the suite is built so a forgotten step fails `pytest` or CI with a message naming the fix, not so you must memorize this page.

## 1. The skill directory

Create `skills/<name>/` with `SKILL.md` at its root; the name is lowercase words joined by hyphens and must equal the directory name.

- `SKILL.md` — the always-loaded router: frontmatter plus purpose, principles, and capability routing.
- `capabilities/<capability>/capability.md` — optional; one per operation for router-shaped skills.
- `references/` — shared reference files the router and capabilities link to.
- `scripts/`, `assets/` — optional; Python is stdlib-only.

The frontmatter must carry these fields, validated by `tests/skills/test_structure_all.py`:

```yaml
---
name: <name> # must equal the directory name
description: >
  ... # ≤1024 chars (spec limit); the suite warns above 800
allowed-tools: Bash Read Grep # space-separated house form
metadata:
  version: "1.0.0" # x-release-please-version
---
```

The `# x-release-please-version` annotation must sit on the version line — it is what lets release-please bump `SKILL.md` when it cuts a release. A router's `allowed-tools` is the union of its capabilities' declarations.

Beyond frontmatter, the structural suite enforces: every `capabilities/<x>/capability.md` on disk is routed from `SKILL.md` and every routed path exists (no orphans in either direction); each capability declares its own `name` and `allowed-tools`; relative markdown links and backtick file paths resolve; capabilities never reference a sibling capability's files — shared material lives in `references/` — and pointers run one way, so a file under `references/` never points into `capabilities/` (name the capability in prose instead; a path there makes the reference unloadable on its own). House conventions apply throughout: skills never reference other skills by name, and prose is one line per paragraph (Prettier `proseWrap: never`). That last one is the only convention here not enforced by the suite — the `lint` workflow's `prettier` job checks it instead, over every `.md` the repo does not ignore, so a new skill's files are covered from the moment they exist on disk. Run `npm run format` before pushing.

Only distributable content may live under `skills/<name>/` — the whole directory ships to consumers via `npx skills` and the release bundles. `tests/skills/test_distribution_hygiene.py` rejects tests, tool configs, and build artifacts tracked inside it.

## 2. The wiring checklist

| # | File | What to add | Backed by |
| --- | --- | --- | --- |
| 1 | `skills/<name>/SKILL.md` | The skill itself (above) | `tests/skills/test_structure_all.py` (working tree) |
| 2 | `tests/skill-corpus/<name>/skill.json` | Description-activation corpus | `tests/skills/test_description_corpora.py` (working tree) + `description-eval` workflow |
| 3 | `manifest.yaml` | Fleet entry: canonical path, type, capabilities | `tests/repo/test_skill_manifest.py` (tracked files) |
| 4 | `release-please-config.json` | Package entry | `tests/release/test_manifest_sync.py` (tracked files) |
| 5 | `.release-please-manifest.json` | Version baseline | `tests/release/test_manifest_sync.py` (tracked files) |
| 6 | `README.md` Skills section | One-line entry | **Nothing — review catches this one** |

Steps 1–2 are validated from the working tree, so they fail a plain `./venv/bin/pytest -q` while you draft, before anything is committed. Steps 3–5 compare against tracked files, so they engage once the skill is staged (`git add`) — run the suite again after staging and every missed wiring point fails with a message naming the file. Step 6 is the one purely manual step: no test reads the README's Skills list, so the PR review must.

### The corpus (step 2)

Every shipped description carries an activation corpus at `tests/skill-corpus/<name>/skill.json`: `target` (the skill name), `kind: "skill"`, and `positive`/`negative` prompt lists, with `_`-prefixed keys free for annotations (the existing corpora record their boundary decisions in a `_comment`). The pytest guards enforce the house floors: at least 8 prompts per side, no duplicates within a side, no prompt on both sides, no prompt shared with another skill's corpus, and varied prompt openings. Draw the negatives from sibling skills' domains so the corpus encodes the real routing decision, not strawmen. After writing it — and after any later description edit — backfill the recorded `description_sha256` with the evaluator from [skill-system-foundry](https://github.com/milanhorvatovic/skill-system-foundry) (`evaluate_descriptions.py tests/skill-corpus --skill-set skills --backfill-hash`): the hash is required by the shape guards, and the `description-eval` workflow blocks on a stale one while scoring precision/recall as advisory.

### The fleet manifest (step 3)

`manifest.yaml` at the repo root declares every skill for skill-system-foundry tooling: the skill name keyed under `skills:`, its `canonical: skills/<name>/SKILL.md` path, its `type` (`router` with a `capabilities:` list, or `standalone`), matching the tracked tree exactly — both directions are asserted, including the capability list.

### Release wiring (steps 4–5)

`release-please-config.json` gains a package entry and `.release-please-manifest.json` a version baseline:

```json
"skills/<name>": {
  "component": "<name>",
  "extra-files": [{ "type": "generic", "path": "SKILL.md" }]
}
```

```json
"skills/<name>": "1.0.0"
```

The manifest value must equal `SKILL.md`'s `metadata.version` — the sync test asserts the equality. Seed both with the version the skill should release from: release-please treats the manifest entry as the last-released baseline and computes the first release by applying the squash commit's type to it (`feat` → minor). To pin the first release to an exact version instead, use a `Release-As: x.y.z` footer as described in [CONTRIBUTING](../CONTRIBUTING.md#versioning).

## 3. What you don't touch

- `skills/<name>/CHANGELOG.md` — release-please creates and owns it; never hand-write one.
- The release workflow's bundle job — it derives the skills to bundle from the release output.
- The `description-eval` workflow — it discovers corpora by path.
- `.gitattributes` — skill directories ship by default; only repo machinery is export-ignored.

## 4. Tests

Do not write structure tests for the new skill: the parametrized suite in `tests/skills/test_structure_all.py` picks it up automatically from its first run. Add a `tests/skills/<snake_name>/` module (the skill name snake_cased — the test directories are Python packages, so hyphens become underscores: `git-toolkit` → `tests/skills/git_toolkit/`) only for content contracts unique to the skill — counts, schemas, or invariants a generic structural check cannot know (for example, coding-principles pins its mantra and principle counts, and git-toolkit validates its NDJSON output schema).

## 5. The pull request

Title the introducing PR with the `repo` scope, not the skill name — the title gate runs from the base branch, where the new skill does not exist yet (see [CONTRIBUTING](../CONTRIBUTING.md#pull-requests)); once the skill is on `main`, later PRs use its name as the scope. Keep the PR to one skill, and run `./venv/bin/pytest -q` with everything staged before pushing — a green run means every guarded wiring point above is in place.
