## ADDED Requirements

### Requirement: Post-commit hook updates CHANGELOG.md on every bump

When the post-commit hook performs a version bump, it SHALL update the configured changelog file by promoting the `[Unreleased]` section into a new `[<new-version>] - <YYYY-MM-DD>` section and recording the originating conventional commit under the appropriate category (Features, Bug Fixes, etc.) before staging the file for the amend.

#### Scenario: feat commit writes a Features entry

- **WHEN** a `feat: add new exporter` commit is finalised and bumps the version from `0.7.0` to `0.8.0`
- **THEN** `CHANGELOG.md` contains a new `## [0.8.0] - <today>` section with `add new exporter` under the Features (or `✨ Features`) heading

#### Scenario: fix commit writes a Bug Fixes entry

- **WHEN** a `fix: parse invalid header` commit is finalised
- **THEN** `CHANGELOG.md` contains a new section for the bumped patch version with `parse invalid header` under the Bug Fixes heading

#### Scenario: breaking change is flagged

- **WHEN** a commit with `BREAKING CHANGE: drop python 3.10` is finalised
- **THEN** the new section contains a `### ⚠ BREAKING CHANGES` (or equivalent) block listing `drop python 3.10`

### Requirement: Changelog write reuses ChangelogManager

The hook SHALL invoke `pezin.core.changelog.ChangelogManager.update_changelog()` rather than re-implement parsing or section ordering. If `CHANGELOG.md` does not exist, the hook SHALL create it with a Keep-a-Changelog-compatible header before delegating to `ChangelogManager`.

#### Scenario: missing CHANGELOG.md is created on first run

- **WHEN** the hook runs on a `feat:` commit in a repo without `CHANGELOG.md`
- **THEN** the hook writes `CHANGELOG.md` with the standard Keep-a-Changelog header AND populates a section for the new version

#### Scenario: existing CHANGELOG.md is preserved

- **WHEN** the hook runs in a repo whose `CHANGELOG.md` already contains historical sections
- **THEN** the new version section is inserted above the previous most recent version and existing sections are not rewritten

#### Scenario: re-running on an already-recorded version is a no-op for that section

- **WHEN** a section for `[<new-version>]` already exists in `CHANGELOG.md`
- **THEN** the hook does not append a duplicate section and does not corrupt the file

### Requirement: Changelog write is staged in the same amend as the version files

After writing `CHANGELOG.md`, the hook SHALL include the changelog path in the list of files passed to `git add` and to the subsequent `git commit --amend --no-edit --no-verify` so the changelog entry is part of the originating commit.

#### Scenario: changelog lands in HEAD

- **WHEN** the post-commit hook bumps a version
- **THEN** `git show HEAD --stat` lists `CHANGELOG.md` alongside the version files and the user's source file

### Requirement: Changelog write is configurable via [tool.pezin.changelog]

The hook SHALL read an optional `[tool.pezin.changelog]` table from `pyproject.toml` (or the active config file) with keys `enabled` (bool, default `true`), `path` (str, default `CHANGELOG.md`), `unreleased_label` (str, default `Unreleased`), and `header_style` (str, default `keepachangelog`). Absence of the table MUST behave identically to an empty table with all defaults.

#### Scenario: enabled = false disables changelog writes

- **WHEN** `[tool.pezin.changelog] enabled = false` is set in `pyproject.toml`
- **THEN** the post-commit hook bumps the version, performs the amend, and creates the tag, but does not touch `CHANGELOG.md`

#### Scenario: custom path is honoured

- **WHEN** `[tool.pezin.changelog] path = "docs/HISTORY.md"` is set
- **THEN** the hook writes the new section to `docs/HISTORY.md` and stages that file for the amend

#### Scenario: defaults apply when no config block is present

- **WHEN** no `[tool.pezin.changelog]` table is present in the project's config
- **THEN** the hook writes to `CHANGELOG.md` at the repo root with the Keep-a-Changelog style

### Requirement: Changelog write failure does not abort the version bump

If the changelog write or staging step raises, the hook SHALL log a warning via `echo_to_terminal`, omit the changelog from the amend, and continue with the version amend so the bump still lands in the commit.

#### Scenario: changelog write raises but version still bumps

- **WHEN** `ChangelogManager.update_changelog()` raises an exception during the hook run
- **THEN** the post-commit hook prints a `[pezin] Warning: CHANGELOG write failed: …` line, completes the amend of the version files only, and exits zero

### Requirement: Monorepo mode writes one changelog per bumped service

In monorepo mode the hook SHALL resolve the changelog path relative to each service's root and write per-service changelog entries. Service-level overrides under `[tool.pezin.services.<name>.changelog]` MUST take precedence over the top-level `[tool.pezin.changelog]` defaults.

#### Scenario: scoped feat updates only that service's changelog

- **WHEN** a `feat(api): …` commit bumps the `api` service from `1.2.0` to `1.3.0` in monorepo mode
- **THEN** only `<api-service-root>/CHANGELOG.md` is updated, other services' changelogs are untouched, and the staged file is included in the amend

#### Scenario: service opts out individually

- **WHEN** `[tool.pezin.services.api.changelog] enabled = false` is set and a `feat(api): …` commit is finalised
- **THEN** the `api` service version is bumped and tagged but its `CHANGELOG.md` is not modified
