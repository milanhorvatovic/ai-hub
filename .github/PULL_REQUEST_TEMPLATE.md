## What & why

<!-- Describe the change and the motivation. Which skill / area does it touch? -->

<!--
PR title = the squash commit subject. Write it as a Conventional Commit scoped by skill:
  feat(git-toolkit): add a release-notes capability
Repo-wide changes use an area scope (release, repo, deps, ci) or none. A CI gate checks it.
-->

## Related issues

Closes #

## Checklist

- [ ] PR title is a Conventional Commit scoped by skill (or repo area)
- [ ] Bumped the touched skill's `metadata.version` for behavior-affecting changes (see [CONTRIBUTING.md](../CONTRIBUTING.md#versioning))
- [ ] Tests added/updated for any skill-shape change
- [ ] `./venv/bin/pytest -q` passes locally
- [ ] Docs / SKILL.md updated where relevant
