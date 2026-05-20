---
name: code-of-conduct
description: >
  Scans, audits, and scaffolds a repository's code of conduct — whether a
  CODE_OF_CONDUCT exists, whether it is based on a recognized standard (the
  Contributor Covenant), and whether it names a real, reachable enforcement
  contact. Audit flags a missing code of conduct and a placeholder enforcement
  contact; scaffold writes CODE_OF_CONDUCT.md from the Contributor Covenant with
  the contact filled in. Triggers on "add a code of conduct", "do we have a
  CoC", "who handles conduct reports", or a full-repo audit.
allowed-tools: Bash Read Grep Glob Write
---

# code-of-conduct capability

Governs the community's behavioral baseline: is there a code of conduct, is it a
standard one contributors recognize, and can someone actually report a problem
to a real person. Reads and judges by default; writes `CODE_OF_CONDUCT.md` only
on confirmation.

## Modes

- **scan** — report the code of conduct present and its enforcement contact.
- **audit** — judge it against `../../references/oss-health-rubric.md`.
- **scaffold** — write `CODE_OF_CONDUCT.md` after confirmation, contact filled.

## Inputs & guards

- Not a git repo → stop.
- A code of conduct already exists → report it; for scaffold, require explicit confirmation and a diff before replacing.
- The enforcement contact is a real-world commitment — never invent one. For scaffold, ask the maintainer for the contact and refuse to write a placeholder.

## Scan

Sources (catalog: `../../references/convention-files.md`), citing each:

1. File: `CODE_OF_CONDUCT.md` at root, `docs/`, or `.github/` (also `.txt` / `.rst`).
2. Standard basis: does the text match the Contributor Covenant (look for its characteristic "Our Pledge" / "Enforcement" structure and version line)?
3. Enforcement contact: the email/URL the document gives for reports; flag obvious placeholders (`[INSERT CONTACT METHOD]`, `email@example.com`).

## Audit

Checks follow the schema in `../../references/oss-health-rubric.md`
(`id` — **severity** [· scorecard: Name]. criterion. why):

- `coc-present` — **should**. Fail when there's no `CODE_OF_CONDUCT`. A public project without one has no stated basis to address abusive behavior.
- `coc-enforcement-contact` — **should**. Fail when the document has no enforcement contact or only a placeholder. An unenforceable code of conduct is decorative.
- `coc-standard-text` — **could**. Pass when based on a recognized standard (Contributor Covenant). Contributors already understand the terms, and it has been legally vetted.

## Scaffold

`CODE_OF_CONDUCT.md` — write after confirmation from
`references/code-of-conduct.template.md` (Contributor Covenant). Replace the
contact placeholder with the maintainer-provided enforcement contact before
writing; do not write the file with a placeholder left in. House style keeps the
file at repo root; GitHub also surfaces it from `.github/`.

For the canonical full text, fetch the current Contributor Covenant rather than
paraphrasing the body.

## Output

Report per `../../references/output-format.md`: scan emits the code-of-conduct inventory with its contact and source; audit emits severity-tagged findings, the domain score, and a `scaffold` offer when missing.

## Edge cases

- **Org-level `.github`** — an org code of conduct may apply fleet-wide; detect and don't duplicate.
- **Existing custom code of conduct** — don't push to replace a deliberate custom one with Contributor Covenant; only flag a missing enforcement contact.
- **Contact is a private alias** — that's fine; the check is "reachable", not "public individual".

## Anti-patterns

- Don't write a `CODE_OF_CONDUCT` with a placeholder contact — get a real one or stop.
- Don't replace an existing code of conduct without confirmation and a diff.
- Don't paraphrase the Contributor Covenant body — use its canonical text.
