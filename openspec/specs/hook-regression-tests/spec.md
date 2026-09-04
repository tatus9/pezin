# hook-regression-tests Specification

## Purpose
TBD - created by archiving change auto-changelog-in-post-commit. Update Purpose after archive.
## Requirements
### Requirement: tests/hooks/ exercises post-commit end-to-end

The repository SHALL include a `tests/hooks/` package containing end-to-end tests that drive the real `prepare-commit-msg` + `post-commit` hook entry points against a throwaway git repository created per test via `tmp_path`.

#### Scenario: tests/hooks/ exists and is discovered

- **WHEN** `pytest` is invoked at the project root
- **THEN** at least one test under `tests/hooks/` is collected and run

#### Scenario: each test uses an isolated git repo

- **WHEN** a hook regression test runs
- **THEN** it creates a new git repo under `tmp_path`, initialises it, installs the hooks, and does not depend on any state outside `tmp_path`

### Requirement: Regression test covers reformatter + pezin interaction

`tests/hooks/` SHALL contain at least one test that installs both pezin and a pre-commit-stage reformatter hook (one that fails on first run, rewrites files, and passes on second run), makes a `feat:` commit, and asserts that the resulting `HEAD` contains the user's source file, every configured version file, AND `CHANGELOG.md`.

#### Scenario: reformatter retry does not leak the bump to the next commit

- **WHEN** the test installs a reformatter pre-commit hook that auto-fixes whitespace on second run, the user makes a `feat: add thing` commit that triggers reformatting (first attempt aborts, files are restaged, second attempt passes)
- **THEN** `git show HEAD --stat` lists the user's source file AND `pyproject.toml` AND the `__version__` file AND `CHANGELOG.md`, and `git status --porcelain` is empty after the commit completes

#### Scenario: subsequent test commit does not inherit a prior bump

- **WHEN** after the feat commit above, the test makes a `test: add coverage` commit (no-bump type)
- **THEN** the test commit contains only the user-staged file and `git show HEAD --stat` does not list `pyproject.toml`, the version file, or `CHANGELOG.md`

### Requirement: Regression test asserts changelog content

The reformatter regression test SHALL also read `CHANGELOG.md` after the feat commit and assert the new version section exists with the commit summary under the appropriate category.

#### Scenario: feat summary appears under Features

- **WHEN** the test makes a `feat: add thing` commit that bumps from `0.0.0` to `0.1.0`
- **THEN** `CHANGELOG.md` contains a `## [0.1.0]` section and the line `add thing` appears under the Features heading within that section

### Requirement: Slow hook tests run under an opt-in marker

End-to-end hook tests that invoke real subprocesses (`git`, `pre-commit`) SHALL be marked `@pytest.mark.slow` and configured so the default `pytest` invocation excludes them, while `pytest -m slow` runs them.

#### Scenario: default pytest run skips slow hook tests

- **WHEN** `pytest` is invoked with no markers
- **THEN** the reformatter regression test is not collected

#### Scenario: opt-in pytest run executes slow hook tests

- **WHEN** `pytest -m slow` is invoked
- **THEN** the reformatter regression test is collected and run
