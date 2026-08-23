# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### 🧰 Maintenance

- pezin's own releases now keep `src/pezin/__init__.py.__version__` in sync
  with `pyproject.toml` via `version_files` (it had drifted to 0.8.0 while
  the package was at 0.8.2).

## [0.8.2] - 2026-08-23

### 🐛 Bug Fixes

- The parked-patch guard now also covers repositories without a pezin
  config file. Projects whose version lives in `package.json` found via
  the config-file fallback (e.g. plain JavaScript apps) were still bumped
  while pre-commit had unstaged changes to that file parked, reintroducing
  the v0.8.1 data-loss path there. README upgrade guidance corrected:
  pinning `rev:` to a tag (not `pre-commit install-hooks`) is what
  refreshes a `rev: HEAD` hook environment.

## [0.8.1] - 2026-08-23

### 🐛 Bug Fixes

- Commit hooks can no longer wipe a repo's unstaged changes. When the
  pre-commit framework has parked unstaged edits to a file pezin would
  rewrite (version files or `CHANGELOG.md`), the post-commit hook now
  skips the bump and explains why, instead of rewriting the file and
  breaking pre-commit's parked-patch restore (which discarded the user's
  unstaged work from the worktree). Unstaged changes to other files keep
  bumping as before. Additionally, a failure inside pezin's own
  bump/amend path now restores the worktree, index and `HEAD` to their
  pre-hook state.

## [0.8.0] - 2026-08-06

### ✨ Features

- Automatic `CHANGELOG.md` updates on commit. The post-commit hook now
  promotes the `[Unreleased]` section into a dated `[<version>]` section
  and lists the originating commit under the matching category, then
  amends the change into the originating commit alongside the version
  files. Configurable via `[tool.pezin.changelog]` (opt-out with
  `enabled = false`); per-service overrides are honoured in monorepo
  mode.
- `pezin install-hooks` now generates scripts that invoke the hooks
  through `typer.run(main)`, fixing the `'OptionInfo' object has no
  attribute 'suffix'` error from the previous `main()` call.

### 🧪 Tests

- Added `tests/hooks/test_post_commit_with_reformatter.py` — an
  end-to-end regression test driven by the real `pre-commit` framework
  that reproduces the reformatter retry / re-stage path and asserts the
  bump + changelog land in a single amend. Tagged `slow`; opt in with
  `pytest -m slow`.

### 🐛 Bug Fixes

- Corrected `__version__` drift in `pezin/__init__.py` (was stuck at
  `0.2.0`).
- Fixed `README.md` pre-commit `rev` pointing at a non-existent tag.

## [0.7.0] - 2026-05-14

### ✨ Features

- Surface version bump feedback through pre-commit capture. The post-commit
  hook now reports the applied bump back through the pre-commit framework
  instead of failing silently.

## [0.6.0] - 2025-12-27

### ✨ Features

- Show all service versions in monorepo mode. `pezin` reports the version
  of every configured service rather than only the first.

## [0.5.0] - 2025-12-27

### ✨ Features

- Switch to modern hooks only. Consolidated the hook surface onto
  `pre-commit` / `post-commit` and retired the legacy `commit-msg` path.

## [0.4.0] - 2025-12-26

### ✨ Features

- Auto amend bumped file version. Version files touched by a bump are now
  folded back into the originating commit via `git commit --amend`.

## [0.3.1] - 2025-12-24

### ✨ Features

- Get version for CI usage. Expose the current version in a form suitable
  for consuming from CI pipelines.

### 🐛 Bug Fixes

- Update GitHub Actions.

## [0.2.1] - 2025-08-01

### ✨ Features

- Support merge flow and commit without params. Conventional-commit
  detection now tolerates merge commits and bare `pezin` invocations.

### 🐛 Bug Fixes

- Code improvements.

## [0.1.1-rc] - 2025-07-27

### ✨ Features

- Support fixup/squash commits.

### 🐛 Bug Fixes

- Missing pezin pre-commit hook.

### 📚 Documentation

- Cleanup.
- Update readme.

## [0.1.0] - 2025-07-24

### 🐛 Bug Fixes

- Missing pezin pre-commit hook.

### 📚 Documentation

- Cleanup.
- Update readme.

## [0.0.3] - 2025-07-24

### 🐛 Bug Fixes

- Missing pezin pre-commit hook.

### 📚 Documentation

- Cleanup.
- Update readme.

[Unreleased]: https://github.com/tatus9/pezin/compare/v0.8.2...HEAD
[0.8.2]: https://github.com/tatus9/pezin/compare/v0.8.1...v0.8.2
[0.8.1]: https://github.com/tatus9/pezin/compare/v0.8.0...v0.8.1
[0.8.0]: https://github.com/tatus9/pezin/compare/v0.7.0...v0.8.0
[0.7.0]: https://github.com/tatus9/pezin/compare/v0.6.0...v0.7.0
[0.6.0]: https://github.com/tatus9/pezin/compare/v0.5.0...v0.6.0
[0.5.0]: https://github.com/tatus9/pezin/compare/v0.4.0...v0.5.0
[0.4.0]: https://github.com/tatus9/pezin/compare/v0.3.1...v0.4.0
[0.3.1]: https://github.com/tatus9/pezin/compare/v0.2.1...v0.3.1
[0.2.1]: https://github.com/tatus9/pezin/compare/v0.1.1-rc...v0.2.1
[0.1.1-rc]: https://github.com/tatus9/pezin/compare/v0.1.0...v0.1.1-rc
[0.1.0]: https://github.com/tatus9/pezin/compare/v0.0.3...v0.1.0
[0.0.3]: https://github.com/tatus9/pezin/releases/tag/v0.0.3
