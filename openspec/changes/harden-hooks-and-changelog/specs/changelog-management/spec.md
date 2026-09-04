## MODIFIED Requirements

### Requirement: Post-commit hook updates CHANGELOG.md on every bump

When the post-commit hook performs a version bump, it SHALL update the
configured changelog file so that the file follows Keep-a-Changelog ordering:
the `## [Unreleased]` section remains directly below the header, a new
`## [<new-version>] - <YYYY-MM-DD>` section is inserted directly below
`[Unreleased]`, entries previously accumulated under `[Unreleased]` are
promoted into the new version section (deduplicated against the originating
commit's own entries; multi-line entries keep their continuation lines), a
fresh empty `[Unreleased]` section is re-created, and the originating
conventional commit is recorded under the appropriate category (Features, Bug
Fixes, etc.) before staging the file for the amend. When the changelog file
already exists, its header content SHALL be preserved verbatim; the configured
header template SHALL only be used when creating the file.
Version-comparison link definitions SHALL be regenerated and emitted exactly
once at the bottom of the file, with no duplicate or stale definitions left
inside version sections.

#### Scenario: feat commit writes a Features entry

- **WHEN** a `feat: add new exporter` commit is finalised and bumps the version from `0.7.0` to `0.8.0`
- **THEN** `CHANGELOG.md` contains a new `## [0.8.0] - <today>` section with `add new exporter` under the Features (or `✨ Features`) heading

#### Scenario: fix commit writes a Bug Fixes entry

- **WHEN** a `fix: parse invalid header` commit is finalised
- **THEN** `CHANGELOG.md` contains a new section for the bumped patch version with `parse invalid header` under the Bug Fixes heading

#### Scenario: breaking change is flagged

- **WHEN** a commit with `BREAKING CHANGE: drop python 3.10` is finalised
- **THEN** the new section contains a `### ⚠ BREAKING CHANGES` (or equivalent) block listing `drop python 3.10`

#### Scenario: Unreleased stays at the top and is promoted

- **WHEN** `CHANGELOG.md` contains `## [Unreleased]` with a `- support plugins` entry above `## [0.7.0] - 2026-05-01`, and a `feat: add exporter` commit bumps to `0.8.0`
- **THEN** the resulting file lists `## [Unreleased]` (empty) directly below the header, followed by `## [0.8.0] - <today>` containing both `add exporter` and `support plugins`, followed by the unchanged `## [0.7.0]` section

#### Scenario: link definitions are consolidated

- **WHEN** `CHANGELOG.md` contains link-definition lines (e.g. `[0.8.2]: https://…/compare/v0.8.1...v0.8.2`) inside or after version sections, and a bump to `0.9.0` occurs
- **THEN** the rewritten file defines each link exactly once, in a single block at the bottom of the file

#### Scenario: multi-line entries survive promotion

- **WHEN** `[Unreleased]` contains a bullet with indented continuation lines and a bump occurs
- **THEN** the promoted entry in the new version section keeps all continuation lines verbatim

#### Scenario: existing header is preserved

- **WHEN** `CHANGELOG.md` exists with a customized header paragraph above the first version heading and a bump occurs
- **THEN** the customized header is byte-for-byte unchanged in the rewritten file

## ADDED Requirements

### Requirement: Changelog link base URL is configurable

The changelog hook SHALL accept a `repo_url` key under
`[tool.pezin.changelog]` (and per-service
`[tool.pezin.services.<name>.changelog]`) used as the base URL for
version-comparison links. When unset, the URL SHALL be derived from the
`origin` git remote.

#### Scenario: explicit repo_url wins over the git remote

- **WHEN** `[tool.pezin.changelog] repo_url = "https://github.com/tatus9/pezin"` is set and a bump writes comparison links
- **THEN** the generated link definitions use that base URL, regardless of the `origin` remote URL
