# community-health — scaffold templates

Intake-surface files for the `community-health` capability. Tailor fields to the project before writing. House style nests these under `.github/`.

## Bug report issue form — `.github/ISSUE_TEMPLATE/bug_report.yml`

```yaml
name: Bug report
description: Report something that isn't working
labels: ["bug"]
body:
  - type: textarea
    id: what-happened
    attributes:
      label: What happened?
      description: What you expected vs. what actually happened.
    validations:
      required: true
  - type: textarea
    id: repro
    attributes:
      label: Steps to reproduce
    validations:
      required: true
  - type: input
    id: version
    attributes:
      label: Version
    validations:
      required: true
```

## Feature request issue form — `.github/ISSUE_TEMPLATE/feature_request.yml`

```yaml
name: Feature request
description: Suggest an idea or improvement
labels: ["enhancement"]
body:
  - type: textarea
    id: problem
    attributes:
      label: Problem
      description: What problem would this solve?
    validations:
      required: true
  - type: textarea
    id: proposal
    attributes:
      label: Proposed solution
```

## Issue template chooser — `.github/ISSUE_TEMPLATE/config.yml`

```yaml
blank_issues_enabled: false
contact_links:
  - name: Questions & support
    url: https://github.com/<owner>/<repo>/discussions
    about: Ask and answer usage questions here.
```

## PR template — `.github/PULL_REQUEST_TEMPLATE.md`

```markdown
## What & why
<Describe the change and the motivation.>

## Related issues
Closes #

## Checklist
- [ ] Tests added/updated
- [ ] Docs updated
- [ ] Lint and tests pass locally
```

## SUPPORT — `.github/SUPPORT.md`

```markdown
# Support

- **Questions / usage:** open a [Discussion](https://github.com/<owner>/<repo>/discussions).
- **Bugs / feature requests:** open an [Issue](https://github.com/<owner>/<repo>/issues).
- **Security:** see [SECURITY.md](SECURITY.md) — do not open a public issue.
```

## FUNDING — `.github/FUNDING.yml` (optional)

```yaml
github: [<username>]
# open_collective: <name>
# custom: ["https://..."]
```
