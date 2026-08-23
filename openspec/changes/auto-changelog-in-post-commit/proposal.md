## Why

An external bug report against pezin's commit-msg auto-amend exposed two gaps that survive the commit-msg → post-commit migration already shipped on `develop`:

1. The report describes pezin as a tool that bumps versions **and writes a `CHANGELOG.md` entry under `[Unreleased]`** in the same commit. Pezin ships `ChangelogManager` (`src/pezin/core/changelog.py`) and exposes it through the CLI (`src/pezin/cli/commands.py:443`), but the post-commit hook (`src/pezin/hooks/post_commit.py`) never calls it. Pezin's own `CHANGELOG.md` is stuck at `v0.1.1-rc` while `pyproject.toml` is at `0.7.0` — the feature exists but is unwired.
2. The reformatter-retry interaction (a reformatting pre-commit hook plus a versioning hook) is the bug class that motivated the migration, yet `tests/` has no `hooks/` directory, so the post-commit path has zero end-to-end coverage. A future refactor could silently re-introduce the staging bug.

Wiring the changelog into the hook closes the documentation/feature gap, and a regression test pins the post-commit + reformatter contract so the original bug class cannot regress.

## What Changes

- Post-commit hook updates `CHANGELOG.md` (creating it if missing) under `[Unreleased]` → new version section with the bumped commit's conventional-commit summary, then stages it alongside the version files before the amend.
- Skip changelog write when `[skip-bump]` footer present, on fixup/squash commits, on merge/rebase, on amend (existing skip flag honoured), and when no bump occurred — same gating already used for version writes.
- New `[tool.pezin.changelog]` config block (all keys optional) to control filename, header style, and emoji-section map; defaults match the `ChangelogManager` defaults already in code.
- Add `tests/hooks/` with a regression test that drives the failing scenario end-to-end: fixture repo with a reformatter pre-commit hook + pezin post-commit hook, make a `feat:` commit, assert `git show HEAD --stat` contains the user's source file, the version files, **and** `CHANGELOG.md` with a populated `[Unreleased]` → version section.
- Update `CLAUDE.md` and `README.md` to document the changelog behaviour and the new config block.

No breaking changes to the public hook surface — `.pre-commit-config.yaml` entries (`pezin-prepare`, `pezin-post`) stay byte-identical. Users only bump `rev:`.

## Capabilities

### New Capabilities
- `version-bumping`: post-commit hook that detects conventional-commit type, bumps configured version files, amends the commit, and creates a tag. Covers the existing behaviour so a baseline spec exists before we layer changelog onto it.
- `changelog-management`: post-commit hook writes/updates `CHANGELOG.md` under `[Unreleased]` → new version section in the same amend that lands the version bump, with configuration knobs under `[tool.pezin.changelog]`.
- `hook-regression-tests`: end-to-end fixtures covering the post-commit hook against pre-commit reformatter interactions, asserting all bump artefacts land in the original commit.

### Modified Capabilities
<!-- none — no prior specs exist in openspec/specs/ -->

## Impact

- Code: `src/pezin/hooks/post_commit.py` (add changelog write + stage step), `src/pezin/core/config.py` (changelog config parsing), `src/pezin/core/changelog.py` (no API change expected; verify `update_changelog` signature handles missing-file create-on-write).
- Tests: new `tests/hooks/` package, fixtures for a throwaway git repo + a reformatter pre-commit shim.
- Docs: `CLAUDE.md` (add changelog section), `README.md` (configuration example), project `CHANGELOG.md` (entry under `[Unreleased]`).
- Dependencies: none added.
- Release: minor bump (`0.7.0` → `0.8.0`) — new feature, no config-key removals.
