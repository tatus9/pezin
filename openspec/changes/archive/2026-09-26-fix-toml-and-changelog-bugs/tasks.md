# Tasks

## 1. Failing regression tests (written first)

- [x] 1.1 Add test in `tests/core/` for `TomlFileHandler.write_version`: a
  `pyproject.toml` with comments and a comment-only `[tool.x]` table is bumped;
  assert the post-write diff is exactly the version line (compare full file content
  against expected). Run it and verify it FAILS against current code (comments
  dropped).
- [x] 1.2 Add tests for the sibling TOML writers: `write_toml_version`
  (`tests/cli/`) and the hook's `update_version` (`tests/hooks/`) each rewriting a
  commented file must change only the version value. Run them and verify they FAIL.
- [x] 1.3 Add test in `tests/core/` for `ChangelogManager.update_changelog`:
  `[Unreleased]` with `### ⚠️ Breaking Changes` + `### ✨ Features` +
  `### 🔧 Refactors` plus a new `feat` commit → breaking section emitted first,
  exactly one Features section (promoted entries merged with the commit's entry),
  refactor entries merged under the canonical `♻️ Refactor` title, no trailing
  unknown-titled duplicates. Verify it FAILS.
- [x] 1.4 Add round-trip test in `tests/core/` for
  `split_unreleased_entries`: a bullet followed by a blank line and an indented
  fenced ```bash block survives a full `update_changelog` promotion unchanged
  (blank line included). Verify it FAILS.

## 2. TOML write fidelity (bug 1)

- [x] 2.1 Add `tomlkit>=0.12` to `[project.dependencies]` in `pyproject.toml`;
  verify `pip install -e .` (or `uv sync`) succeeds and `python -c "import
  tomlkit"` works.
- [x] 2.2 Convert `TomlFileHandler.write_version`
  (`src/pezin/core/handlers.py`) to parse with tomlkit, set the found dotted key,
  write back — no `tomli_w` round-trip. Verify test 1.1 passes and the existing
  handler tests (`pytest tests/core/ -k handler`) stay green.
- [x] 2.3 Convert `write_toml_version` (`src/pezin/cli/commands.py`) the same
  way. Verify its test from 1.2 passes and `pytest tests/cli/` stays green.
- [x] 2.4 Convert the hook's `update_version` (`src/pezin/hooks/pre_commit.py`)
  the same way, keeping the `git add` staging and error handling intact. Verify its
  test from 1.2 passes and `pytest tests/hooks/ -m "not slow"` stays green.

## 3. Changelog promotion fixes (bugs 2 and 3)

- [x] 3.1 Implement the title-normalization helper (casefold, strip emoji/symbols
  and U+FE0F, naive singular/plural folding) in `src/pezin/core/changelog.py` and
  use it in `update_changelog` to merge promoted subsections under canonical
  configured titles, deduplicated, keeping emission order (configured first,
  unknown after, breaking first under default config). Verify test 1.3 passes AND
  the existing canonical-title changelog tests pass unchanged (compatibility
  guarantee).
- [x] 3.2 Fix `split_unreleased_entries` to append blank lines while an entry is
  open and trim only trailing blanks at flush. Verify test 1.4 passes and
  `pytest tests/core/ -k changelog` is green.

## 4. Wrap-up

- [x] 4.1 Add a CHANGELOG.md entry for this fix under `[Unreleased]` in the pezin
  repo itself; verify the file renders valid Keep-a-Changelog structure.
- [x] 4.2 Run the full test suite (`pytest`, including slow e2e) and
  `ruff check --fix && ruff format`; verify everything is green and clean.
- [x] 4.3 Run `openspec validate fix-toml-and-changelog-bugs --strict`; verify it
  passes.
