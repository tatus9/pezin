# Spec Delta

## ADDED Requirements

### Requirement: Version file rewrites preserve unrelated content

Whenever pezin writes a new version into a user's TOML file — via the file handler
used by the post-commit hook, via the CLI's manual bump, or via any other code path —
the write SHALL change only the version value. Comments, key order, whitespace and
formatting, and empty or comment-only tables SHALL remain byte-identical. The diff
produced by a version bump SHALL be exactly the line(s) carrying the version value.

#### Scenario: comments and comment-only tables survive a bump

- **WHEN** a `pyproject.toml` containing comments and a comment-only table (a table
  whose body is only comments, e.g. `[tool.pezin]` with remarks about defaults) is
  bumped from `0.75.0` to `0.76.0` by the post-commit hook
- **THEN** the comments and the comment-only table are still present after the write,
  and the file diff contains only the changed version value

#### Scenario: manual CLI bump preserves formatting

- **WHEN** the CLI's bump command rewrites a commented TOML version file
- **THEN** comments, key order and formatting are unchanged and only the version value
  differs

#### Scenario: hook-side TOML writer preserves formatting

- **WHEN** the hook's own version-update code path rewrites a commented TOML version
  file
- **THEN** comments, key order and formatting are unchanged and only the version value
  differs
