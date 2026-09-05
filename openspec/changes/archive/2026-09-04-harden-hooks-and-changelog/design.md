## Context

`pezin install-hooks` writes `prepare-commit-msg` and `post-commit` scripts
whose shebang is `#!/usr/bin/env python3`. pezin is typically installed inside
a virtualenv (pipx, `uv tool`, a project venv), so that ambient `python3`
cannot `import pezin`. The generated script then prints
`Error: Could not find pezin package` and exits 1 — for `prepare-commit-msg`
this aborts the commit itself, leaving the repo uncommitable until the user
fixes their PATH. Verified in a scratch repo on 2026-09-04: same flow works
only when the installing venv is first on PATH.

Independently, `ChangelogManager.update_changelog()` writes
`header + new version section + all previous sections`. Because the previous
`[Unreleased]` section is emitted after the new version section, `[Unreleased]`
sinks to the bottom of the file and any entries accumulated under it are never
promoted — the exact behavior the changelog-management spec forbids.
`get_pezin_version()` prefers `importlib.metadata.version("pezin")`, which is
frozen at install time for editable installs, so `pezin --version` can report
an older version than the code.

## Goals / Non-Goals

**Goals:**
- Generated hooks run under the interpreter that installed them.
- A missing pezin install degrades to a warning, never a blocked commit.
- Changelog output matches Keep-a-Changelog ordering and promotion semantics.
- `--version` always matches the synced `pezin.__version__` version file.
- `python -m pezin` works.

**Non-Goals:**
- No changes to the pre-commit framework path (`.pre-commit-hooks.yaml`
  entries already run inside pre-commit's own venv).
- No changelog format redesign beyond ordering/promotion/header preservation.
- No new config keys.

## Decisions

1. **Shebang = `sys.executable` at install time.** The hook template receives
   the absolute path of the interpreter running `pezin install-hooks`. This is
   the same interpreter that just resolved pezin, so the hook import is
   deterministic. Alternative considered — keeping `env python3` and expanding
   the `sys.path` search — rejected: guessing locations is fragile and still
   fails when dependencies (loguru, typer) live only in the venv.
2. **Import failure exits 0 with a loud stderr warning.** A hook's job is to
   assist versioning, not to gate commits. `prepare-commit-msg` blocking
   commits is the worst observed failure mode. The warning tells the user to
   re-run `pezin install-hooks` from the right environment. The existing
   `sys.path` fallback for source checkouts stays (it helps when hooks are
   installed from a pezin dev checkout).
3. **Changelog ordering: rebuild as `header + [Unreleased] + versions
   (newest first)`.** `update_changelog()` promotes the current
   `[Unreleased]` entries by merging them with the new commit's entries into
   the new version section, then re-emits an empty `## [Unreleased]` at the
   top. When the file already exists, its header (everything above the first
   version heading) is preserved verbatim instead of being replaced by
   `config.header_template`; the template is only used when creating the file.
4. **`--version` prefers `pezin.__version__`.** `src/pezin/__init__.py` is a
   configured `version_file`, so it is authoritative and always in sync;
   `importlib.metadata` remains the fallback for exotic installs.
5. **`__main__.py` delegates to `pezin.cli.main:run`.** One-liner, mirrors the
   console script, enables `python -m pezin`.

## Risks / Trade-offs

- [Hooks break if the venv is moved/deleted after install] → The import
  failure path warns and exits 0; `pezin hooks-status` / reinstall recovers.
- [Pinned shebang is less portable across machines sharing a `.git` dir] →
  Acceptable; hooks are machine-local by nature, and re-running
  `pezin install-hooks` rewrites them.
- [Merging `[Unreleased]` entries with hook-recorded entries may duplicate a
  line if the user pre-recorded the same commit] → Deduplicate identical
  formatted lines within the new section.
- [Header preservation keeps user edits but also keeps stale intro text] →
  Acceptable; predictable beats clobbering.

## Migration Plan

1. Land code + tests; run fast suite plus slow hook e2e.
2. Re-run `pezin install-hooks` in consuming repos to refresh shebangs
   (documented in the changelog entry).
3. Release as 0.9.0 (`python -m pezin` is a feature; the rest are fixes).

## Open Questions

None — all decisions above were validated against the scratch-repo repro.
