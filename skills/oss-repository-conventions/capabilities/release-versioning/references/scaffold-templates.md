# release-versioning — scaffold templates

Release-process files for the `release-versioning` capability. These define the _structure_; the prose of any specific release is the change-narration domain.

## `CHANGELOG.md` (Keep a Changelog + SemVer)

```markdown
# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
### Changed
### Fixed

## [0.1.0] - YYYY-MM-DD

### Added
- Initial release.

[Unreleased]: https://github.com/<owner>/<repo>/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/<owner>/<repo>/releases/tag/v0.1.0
```

## release-please — `.github/workflows/release-please.yml`

```yaml
name: release-please
on:
  push:
    branches: [main]
permissions:
  contents: write
  pull-requests: write
jobs:
  release-please:
    runs-on: ubuntu-latest
    steps:
      - uses: googleapis/release-please-action@<sha>   # v4
        with:
          release-type: <node|python|rust|simple>
```

Pair with `release-please-config.json` + `.release-please-manifest.json` for monorepos or non-default layouts.

## Release-notes template — `.github/RELEASE_NOTES_TEMPLATE.md` (house style)

```markdown
## Highlights
<One or two sentences on the theme of this release.>

## Changes
<Grouped by Added / Changed / Fixed / Removed — generated from the changelog.>

## Upgrade notes
<Breaking changes and migration steps, if any.>
```
