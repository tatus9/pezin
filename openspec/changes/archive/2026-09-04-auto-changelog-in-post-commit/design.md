## Context

Pezin already migrated off the buggy `commit-msg` stage (recent commits `e077c66` *switch to modern hooks only* and `21ee4a7` *auto amend bumped file version*) and now runs at `prepare-commit-msg` + `post-commit`. The original commit-msg auto-amend bug — where `git add` inside commit-msg targeted the wrong index under pre-commit's stash wrap — no longer applies because `post-commit` fires **after** pre-commit's stash-restore. The amend uses `--no-verify` to break recursion and is guarded by `.pezin_post_commit_lock` and `.pezin_skip_version_bump` flags.

What did **not** migrate is the changelog write that the external report (and the project's own `CHANGELOG.md` header) implies pezin performs. `ChangelogManager.update_changelog()` exists in `src/pezin/core/changelog.py:224` and is reachable through the `pezin update-changelog` CLI command (`src/pezin/cli/commands.py:443`) and the `bump` CLI (`src/pezin/cli/main.py:449`), but `update_version_and_amend()` in `src/pezin/hooks/post_commit.py:356` never imports or calls it. Result: the project ships at v0.7.0 with a `CHANGELOG.md` whose newest section is `[0.1.1-rc] - 2025-07-27`.

Additionally `tests/hooks/` does not exist, so there is no fixture that exercises the post-commit path against a reformatter pre-commit hook. The bug class that prompted the migration is unprotected by tests.

## Goals / Non-Goals

**Goals:**
- Single amend lands version files + `CHANGELOG.md` in the originating commit.
- Changelog generation reuses `ChangelogManager` — no duplicate parsing logic in the hook.
- New `[tool.pezin.changelog]` config block is fully optional; existing pyproject configs keep working unchanged.
- End-to-end regression test reproduces the reformatter-retry scenario from the external bug report and pins the contract.
- Public hook surface (`.pre-commit-hooks.yaml` entries, hook stage names, CLI commands) stays unchanged.

**Non-Goals:**
- Rewriting `ChangelogManager` or its category map.
- Restoring or shimming the removed commit-msg-stage hook (it's gone, intentionally).
- Generating release notes from a range of commits (existing `pezin update-changelog --since-tag` already covers that path).
- Multi-changelog support in monorepo mode beyond what `ServiceVersionManager` already exposes.

## Decisions

### Decision 1: Single amend, not a second commit

The post-commit hook will write `CHANGELOG.md` **before** the existing `git add` + `git commit --amend --no-edit --no-verify` step, so the version files and changelog land in one amend. The alternative — write changelog, then issue a second amend — costs an extra SHA rewrite, breaks the lock-file invariant (one amend per post-commit run), and increases recursion risk. The current flow already stages a list of files; appending the changelog path to that list is a one-line change.

### Decision 2: Reuse `ChangelogManager.update_changelog()` as-is

`ChangelogManager` already supports create-on-write through `cli/commands.py:462` (writes `# Changelog\n\n## [Unreleased]\n` if missing). The hook will call the same path. If the existing manager API turns out to need a small adjustment for the missing-file case, that change lives in `core/changelog.py` and remains backwards-compatible with the CLI caller.

### Decision 3: Config under `[tool.pezin.changelog]`, all keys optional

```toml
[tool.pezin.changelog]
enabled = true                          # default: true; set false to skip
path = "CHANGELOG.md"                   # default: CHANGELOG.md at repo root
unreleased_label = "Unreleased"         # default matches ChangelogConfig
header_style = "keepachangelog"         # default matches ChangelogConfig
```

Absence of the block = defaults (changelog enabled). This means projects upgrading to the new version automatically get changelog updates — that is intentional, since the feature is the headline of this change. Projects that don't want it set `enabled = false`. Considered: opt-in default (off until configured). Rejected because the project's own `CHANGELOG.md` proves the feature is expected but missing — landing it off-by-default would leave the gap.

### Decision 4: Monorepo mode writes one changelog per service

In monorepo mode (`is_monorepo_mode(pezin_config)`), `ServiceVersionManager.bump_services()` returns a `BumpResult` per service. Each service spec already carries its own root; the changelog path is resolved relative to that service root unless `[tool.pezin.services.<name>.changelog.path]` overrides. If a service has `changelog.enabled = false`, that service is skipped. Considered: single repo-root changelog aggregating all services. Rejected because monorepos typically ship per-service notes and shared changelog files create merge churn.

### Decision 5: Regression test uses real `pre-commit` framework

`tests/hooks/test_post_commit_with_reformatter.py` will spin up a throwaway git repo via `tmp_path`, install both pezin (as a `local` repo entry pointing at the workspace) and a tiny reformatter hook that rewrites whitespace on the staged file. Test asserts `git show HEAD --stat` contains the source file, version files, and `CHANGELOG.md`. Using the real `pre-commit` binary (already a project dependency, `pyproject.toml:21`) is slower than mocking the wrap but is the only way to exercise the stash/restore interaction that motivated the migration. Test is marked `@pytest.mark.slow` and excluded from the default unit-test run.

### Decision 6: Skip gating reuses existing flags

Changelog write is gated by the same conditions that already gate version writes: `should_skip_hook()`, `.pezin_skip_version_bump`, `is_lock_active()`, fixup/squash check, `[skip-bump]` footer, and `convert_bump_type() is None`. No new skip surface. If `update_version_and_amend` returns `None`, no changelog write happens — keeps the two operations atomic.

## Risks / Trade-offs

- **[Changelog write fails after version write succeeds]** → Wrap the changelog write in a try/except inside `update_single_version` / `update_monorepo_versions`. On failure, log a clear warning via `echo_to_terminal`, **skip** staging the changelog, and continue with the amend so the version bump still lands. The user can rerun `pezin update-changelog` manually. Rationale: a half-applied bump is worse than a missing changelog entry.
- **[Real `pre-commit` in tests is slow]** → Marker + opt-in via `pytest -m slow`. Default `pytest` run stays fast; CI gets a separate job for the slow tier.
- **[Existing projects that hand-maintain `CHANGELOG.md`]** → Behaviour change on upgrade: post-commit will start editing the file. Documented in `CHANGELOG.md` under `[Unreleased]` for this change and in the README's upgrade section. Opt-out is `enabled = false`.
- **[`ChangelogManager` writes a duplicate section if rerun on the same commit]** → The amend path is one-shot per post-commit run (lock file), but if a user manually amends after pezin, then re-pushes through pezin via another mechanism, a duplicate could appear. `ChangelogManager` already deduplicates by version header — verify with a test; if not, fix the dedupe upstream and call it from the hook.
- **[Monorepo + global changelog config]** → If a project sets `[tool.pezin.changelog]` at the top level in monorepo mode but no per-service overrides, every service uses the same config. Documented as the intended default.

## Migration Plan

- Implement and merge under v0.8.0 (minor bump; no breaking changes).
- README upgrade note: "Pezin now writes `CHANGELOG.md` automatically on commit. To opt out, add `[tool.pezin.changelog] enabled = false` to `pyproject.toml`."
- `CHANGELOG.md` `[Unreleased]` section gets an entry describing the new behaviour.
- No deprecation shim needed — the old commit-msg-stage hook id has already been removed and is not coming back.
