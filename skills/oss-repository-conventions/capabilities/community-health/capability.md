---
name: community-health
description: >
  Scans, audits, and scaffolds a repository's community-health files — issue
  templates and issue forms, the pull-request template, SUPPORT, FUNDING,
  GitHub Discussions, and triage labels. Audit flags unstructured issues (no
  templates), a missing PR template, and absent triage labels; scaffold writes
  issue forms, a PR template, SUPPORT, and FUNDING. Triggers on "add issue
  templates", "set up a PR template", "where do users get support", "enable
  funding", "set up labels", or a full-repo audit.
allowed-tools: Bash Read Grep Glob Write
---

# community-health capability

Governs the day-to-day intake surfaces: are issues and PRs structured, can users find support, and is triage set up. These are the files GitHub aggregates into a repo's community profile. Reads and judges by default; writes the health files only on confirmation.

## Modes

- **scan** — report the community-health files and settings present.
- **audit** — judge them against `../../references/oss-health-rubric.md` (and GitHub's own community-profile %).
- **scaffold** — write issue forms / PR template / SUPPORT / FUNDING after confirmation.

## Inputs & guards

- Not a git repo → stop.
- This capability covers the PR _template_ (a repo convention file), not authoring any individual PR — that's the change-narration domain.
- Discussions/label state needs `gh`; without it, mark those checks `unknown — gh not available`.
- FUNDING is opt-in and only meaningful for public repos — never push it; offer it as a `could`.

## Scan

Sources (catalog: `../../references/convention-files.md`), citing each:

1. Issues: `.github/ISSUE_TEMPLATE/*.md`, issue forms `.github/ISSUE_TEMPLATE/*.yml`, and `.github/ISSUE_TEMPLATE/config.yml`.
2. PRs: `.github/PULL_REQUEST_TEMPLATE.md` (and the `PULL_REQUEST_TEMPLATE/` multi-template dir).
3. Support & funding: `SUPPORT.md` / `.github/SUPPORT.md`, `.github/FUNDING.yml`.
4. Settings (`gh`): Discussions on (`gh api repos/{owner}/{repo} --jq .has_discussions`); triage labels (`gh label list`).
5. Compare against GitHub's community-profile when available: `gh api repos/{owner}/{repo}/community/profile --jq .health_percentage`.
6. Recognition: `.all-contributorsrc` (the all-contributors spec for crediting non-code contributors).

## Audit

Checks follow the schema in `../../references/oss-health-rubric.md` (`id` — **severity** [· scorecard: Name]. criterion. why):

- `issue-templates` — **should**. Fail when there are no issue templates/forms. Unstructured issues lack repro steps and version info, slowing triage.
- `pr-template` — **should**. Fail when there's no `PULL_REQUEST_TEMPLATE`. A template makes PRs describe what changed and link issues consistently.
- `labels-triage` — **could**. Pass when triage labels exist (`bug`, `enhancement`, `good first issue`, `help wanted`). Enables sorting and newcomer routing.
- `support-doc` — **could**. Pass when `SUPPORT.md` directs help-seeking off the issue tracker (discussions, chat, docs). Keeps issues for defects.
- `funding` — **could** (public repos only). Pass when `FUNDING.yml` is present if the maintainer wants sponsorship. Purely optional.
- `all-contributors` — **could**. Pass when non-code contributions are recognized (the all-contributors spec/bot, or an equivalent Contributors section). Credits docs, design, and triage, not just commits.

## Scaffold

Templates live in `references/scaffold-templates.md` (bug-report and feature issue forms, `config.yml`, PR template, SUPPORT, FUNDING). Write after confirmation, one file at a time. Prefer **issue forms** (YAML) over plain markdown templates — they collect structured fields. Tailor fields to the project (e.g. version dropdown from real releases). House style nests these under `.github/`.

## Output

Report per `../../references/output-format.md`: scan emits the community-health inventory plus the GitHub community-profile %; audit emits severity-tagged findings, the domain score, and a `scaffold` offer for each unmet check.

## Edge cases

- **Org `.github` defaults** — org-level issue/PR templates and SUPPORT apply when the repo has none; detect and don't duplicate.
- **Discussions disabled deliberately** — don't flag `support-doc` as failing just because Discussions is off; SUPPORT can point elsewhere.
- **Internal/private repo** — drop `funding`; relax templates to `could` if the audience is a small known team.

## Anti-patterns

- Don't author or edit individual issues/PRs — only the templates.
- Don't push FUNDING — it's opt-in.
- Don't pass discussions/label checks as satisfied when `gh` is unavailable — mark them `unknown`.
- Don't overwrite existing templates without a diff.
