## ADDED Requirements

### Requirement: Post-commit hook bumps version on conventional commits

The post-commit hook SHALL parse the message of `HEAD`, determine the conventional-commit type, and bump the configured version files when the type maps to a non-`NONE` `BumpType`. The mapping MUST be: `feat` → MINOR, `fix` → PATCH, `feat!` or any commit with `BREAKING CHANGE:` footer → MAJOR, and `chore` / `docs` / `style` / `refactor` / `test` / `ci` / `build` / `perf` → no bump.

#### Scenario: feat commit bumps minor

- **WHEN** a `feat: …` commit is finalised and the post-commit hook runs
- **THEN** the configured version files are updated from `MAJOR.MINOR.PATCH` to `MAJOR.(MINOR+1).0` and staged for amendment

#### Scenario: fix commit bumps patch

- **WHEN** a `fix: …` commit is finalised
- **THEN** the configured version files are updated to `MAJOR.MINOR.(PATCH+1)` and staged for amendment

#### Scenario: breaking change bumps major

- **WHEN** a commit message contains `BREAKING CHANGE:` in the footer or uses the `feat!:` / `fix!:` form
- **THEN** the configured version files are updated to `(MAJOR+1).0.0` and staged for amendment

#### Scenario: chore commit does not bump

- **WHEN** a `chore: …` commit is finalised
- **THEN** no version files are written, no amendment is performed, and no tag is created

### Requirement: Post-commit hook amends version files into the originating commit

After writing version files, the hook SHALL `git add` each updated file and run `git commit --amend --no-edit --no-verify` so the bumped artefacts land inside the commit that triggered the hook rather than leaking into the next commit's staging area.

#### Scenario: bumped files land in HEAD

- **WHEN** the post-commit hook bumps a version for a `feat: …` commit
- **THEN** `git show HEAD --stat` lists the user's source file AND every configured version file

#### Scenario: amend uses --no-verify to avoid hook recursion

- **WHEN** the hook performs the amend
- **THEN** the amend subprocess is invoked with `--no-verify` so pre-commit hooks do not re-run and trigger another post-commit invocation

#### Scenario: lock file prevents reentry

- **WHEN** the post-commit hook is invoked while `.pezin_post_commit_lock` exists in the repo root
- **THEN** the hook exits zero without writing files, performing an amend, or creating a tag

### Requirement: Post-commit hook skips non-bump scenarios

The hook SHALL skip version bumping for: merge commits, in-progress rebase or cherry-pick operations, fixup or squash commits, commits whose footer contains `[skip-bump]`, and when `.pezin_skip_version_bump` exists (written by `prepare-commit-msg` when an amend is detected).

#### Scenario: amend detected via skip flag

- **WHEN** `prepare-commit-msg` detects `git commit --amend` and writes `.pezin_skip_version_bump`
- **THEN** the subsequent post-commit hook reads the flag, removes it, and exits without bumping or writing the changelog

#### Scenario: merge commit skips bump

- **WHEN** the hook runs on a commit that has two parents (`HEAD^2` resolves)
- **THEN** the hook exits without bumping or writing the changelog

### Requirement: Post-commit hook creates an annotated tag for the new version

When a bump occurs and the `--create-tag` flag is true (default), the hook SHALL create an annotated tag named `v{version}` for single-repo mode or the service-specific tag name for monorepo mode, unless a tag with that name already exists.

#### Scenario: new tag created

- **WHEN** the version bumps from `0.7.0` to `0.8.0` and no tag `v0.8.0` exists
- **THEN** an annotated tag `v0.8.0` with message `Release 0.8.0` is created on the amended commit

#### Scenario: existing tag is not overwritten

- **WHEN** a tag `v0.8.0` already exists in the repository
- **THEN** the hook logs the conflict, does not move or overwrite the tag, and continues without error
