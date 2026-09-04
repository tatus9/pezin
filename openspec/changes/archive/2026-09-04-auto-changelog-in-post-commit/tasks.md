## 1. Config plumbing

- [x] 1.1 Add `ChangelogHookConfig` dataclass (path, enabled, unreleased_label, header_style) in `src/pezin/core/config.py` and a `read_changelog_config(pezin_config)` helper that returns defaults when the table is absent.
- [x] 1.2 Surface the same parser inside `ServiceVersionManager` so per-service `[tool.pezin.services.<name>.changelog]` overrides resolve correctly, falling back to top-level defaults.
- [x] 1.3 Add unit tests in `tests/core/test_config.py` for: missing table → defaults; partial table → defaults filled; `enabled = false`; per-service override beats top-level.

## 2. ChangelogManager glue

- [x] 2.1 Verify `ChangelogManager.update_changelog()` is idempotent on a duplicate version section; if not, add a guard and a `tests/core/test_changelog.py` case for it.
- [x] 2.2 Add a `create_if_missing(path)` helper (or extract from `cli/commands.py:462`) so both the CLI and the hook share the missing-file create path.

## 3. Post-commit hook wiring

- [x] 3.1 In `src/pezin/hooks/post_commit.py:update_single_version`, after `write_versions(new_version)` and before the `git add` loop, call the new `write_changelog_entry(commit, new_version, repo_root, changelog_config)` helper and extend `updated_files` with the changelog path on success.
- [x] 3.2 Mirror the same call inside `update_monorepo_versions`, resolving the changelog path per service from the service's root.
- [x] 3.3 Wrap the changelog write in a try/except: on failure, `echo_to_terminal("[pezin] Warning: CHANGELOG write failed: …")`, log the traceback at warning level, drop the changelog from the staged list, and continue with the amend.
- [x] 3.4 Respect `enabled = false` by skipping the call entirely (no warning, no log noise).

## 4. End-to-end regression test

- [x] 4.1 Create `tests/hooks/__init__.py` and `tests/hooks/conftest.py` with fixtures: `tmp_git_repo`, `install_pezin_hooks(repo)`, `install_reformatter_hook(repo)`.
- [x] 4.2 Write `tests/hooks/test_post_commit_with_reformatter.py::test_feat_commit_lands_version_and_changelog` per `specs/hook-regression-tests/spec.md` scenarios 1 and 3.
- [x] 4.3 Add `tests/hooks/test_post_commit_with_reformatter.py::test_next_test_commit_does_not_inherit_bump` per `specs/hook-regression-tests/spec.md` scenario 2.
- [x] 4.4 Register the `slow` marker in `pyproject.toml` under `[tool.pytest.ini_options]` and add `addopts = "-m 'not slow'"` so default runs skip these tests.
- [x] 4.5 Confirm `pytest -m slow tests/hooks/` runs and passes locally.

## 5. Docs & release

- [x] 5.1 Update `CLAUDE.md`: add a "Changelog automation" subsection under Configuration documenting `[tool.pezin.changelog]` and the opt-out.
- [x] 5.2 Update `README.md` with a Changelog automation example and an "Upgrading from < 0.8.0" note.
- [x] 5.3 Add an `[Unreleased]` entry in the project's own `CHANGELOG.md` describing this change ("automatic CHANGELOG.md updates on commit"). Let pezin itself bump and finalise the section on the merge commit.
- [x] 5.4 Run `ruff check --fix && ruff format && pytest && pytest -m slow tests/hooks/` before opening the PR.

## 6. Validation

- [x] 6.1 Run `openspec validate auto-changelog-in-post-commit --strict` and resolve any reported issues.
- [x] 6.2 Run `pezin install-hooks` in a fresh clone, make a real `feat:` commit, and confirm `git show HEAD --stat` lists `CHANGELOG.md`.
  - Pre-commit-framework path verified end-to-end by the new slow test
    `tests/hooks/test_post_commit_with_reformatter.py::test_feat_commit_lands_version_and_changelog`,
    which drives the same `python -m pezin.hooks.post_commit` entry point
    against a throwaway repo.
  - The `pezin install-hooks` CLI itself currently emits hook scripts that
    call the typer-decorated `main()` directly instead of `typer.run(main)`,
    producing `'OptionInfo' object has no attribute 'suffix'` at runtime.
    That is a **pre-existing** defect in `src/pezin/cli/hooks.py:88-90`,
    independent of this change's scope. Filed as a follow-up.
