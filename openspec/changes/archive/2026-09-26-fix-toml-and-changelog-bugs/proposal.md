# Proposal

## Why

The v0.9.0 post-commit hook corrupted a downstream repo (doodoo 0.75.0 → 0.76.0) in three
ways: the TOML version bump silently deleted comments and comment-only tables from
`pyproject.toml`; hand-written changelog subsections with slightly different titles
(e.g. `### ⚠️ Breaking Changes`) were sorted below the configured sections instead of
merging under them; and blank lines inside multi-line changelog bullets were dropped,
gluing bullets to their indented fenced code blocks. Pezin must never rewrite parts of a
user's file it was not asked to touch.

## What Changes

- **Bug 1 — TOML round-trip destroys formatting**: `TomlFileHandler.write_version`
  (`src/pezin/core/handlers.py`) stops round-tripping the whole file through
  `tomli.load` + `tomli_w.dump`. It uses `tomlkit` (round-trip preserving) so only the
  version value changes; comments, key order, formatting and empty/comment-only tables
  stay byte-identical. The two sibling `tomli_w` writers that rewrite user files are
  fixed the same way: `write_toml_version` (`src/pezin/cli/commands.py`) and the hook's
  `update_version` (`src/pezin/hooks/pre_commit.py`). `tomlkit` is added as a runtime
  dependency.
- **Bug 2 — Loose section-title matching on promotion**: `update_changelog`
  (`src/pezin/core/changelog.py`) matches promoted `[Unreleased]` subsection titles to
  configured sections loosely — casefolded, with emoji and variation selectors
  (U+FE0F) stripped, and singular/plural treated as equal (`Breaking Changes` ≈
  `BREAKING CHANGES`, `Refactors` ≈ `Refactor`). Matched entries merge under the
  canonical configured title; breaking changes are always emitted first; unknown titles
  still go after the known ones in original order.
- **Bug 3 — Blank lines in multi-line entries**: `split_unreleased_entries`
  (`src/pezin/core/changelog.py`) keeps blank lines between a bullet and its indented
  continuation (fenced ``` blocks, sub-paragraphs); only trailing blank lines before
  the next bullet/heading are dropped. Entries round-trip unchanged.
- A failing regression test is written first for each bug, then the fix. A CHANGELOG.md
  entry for the pezin repo itself is added.

Not changing: behavior for changelogs that already use the canonical section titles;
the post-commit auto-amend flow; the parked-patch data-loss guard.

## Capabilities

### New Capabilities

_(none)_

### Modified Capabilities

- `version-bumping`: version file rewrites (TOML) must preserve everything except the
  version value — comments, key order, formatting and empty/comment-only tables stay
  byte-identical. Currently the spec is silent on rewrite fidelity, which allowed the
  destructive `tomli_w` round-trip.
- `changelog-management`: `[Unreleased]` promotion must merge loosely-titled
  subsections under canonical configured titles (breaking first) and must preserve
  blank lines inside multi-line entries. Existing scenarios cover continuation lines
  and promotion but not title fuzziness or blank-line preservation.

## Impact

- **Code**: `src/pezin/core/handlers.py`, `src/pezin/core/changelog.py`,
  `src/pezin/cli/commands.py`, `src/pezin/hooks/pre_commit.py`.
- **Dependencies**: add `tomlkit` to `[project.dependencies]` in `pyproject.toml`
  (present in the dev environment as 0.15.1; `tomli`/`tomli_w` remain for pure-data
  reads/writes that never rewrite user files).
- **Tests**: new failing-then-green tests in `tests/core/` (handlers, changelog);
  cover the sibling CLI and hook writers; full suite must pass.
- **Users**: downstream repos keep their hand-written TOML comments and changelog
  structure; no configuration changes, no breaking API changes.
