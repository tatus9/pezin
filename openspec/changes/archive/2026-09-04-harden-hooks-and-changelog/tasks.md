## 1. Hook interpreter pinning (hook-installation spec)

- [x] 1.1 In `src/pezin/cli/hooks.py:create_hook_script`, generate the script with `#!{sys.executable}` (absolute, resolved at install time) instead of `#!/usr/bin/env python3`; keep the existing `sys.path` fallback for source checkouts.
- [x] 1.2 Change the generated script's import-failure path to print a loud stderr warning advising `pezin install-hooks` re-run and exit 0 instead of `sys.exit(1)`.
- [x] 1.3 Unit tests in `tests/cli/test_hooks_install.py`: shebang equals `sys.executable` of the installing process; generated script contains the graceful-exit warning text.

## 2. Changelog ordering and promotion (changelog-management spec)

- [x] 2.1 Refactor `ChangelogManager.update_changelog()` in `src/pezin/core/changelog.py`: preserve the existing file header verbatim; emit `## [Unreleased]` (empty) below the header; insert the new version section next; keep older sections newest-first; promote `[Unreleased]` entries into the new version section with dedupe against the current commit's formatted lines.
- [x] 2.2 Extract header detection (content above the first version heading) into a testable helper.
- [x] 2.3 Update/extend `tests/core/test_changelog.py`: Unreleased-at-top scenario, promotion scenario (spec scenario 4), header-preservation scenario, idempotency guard still holds, second bump keeps order (0.9.0 above 0.8.0).

## 3. CLI accuracy and entry point

- [x] 3.1 Rewrite `get_pezin_version()` in `src/pezin/cli/main.py` to prefer `pezin.__version__`, falling back to `importlib.metadata` then the pyproject dev fallback; adjust `tests/cli/test_cli.py` accordingly.
- [x] 3.2 Add `src/pezin/__main__.py` delegating to `pezin.cli.main:run`; add a test that `python -m pezin --version` exits 0 and prints the `__version__`.

## 4. Slow e2e: generated hooks commit without venv on PATH

- [x] 4.1 Add slow test in `tests/hooks/`: scratch repo, `pezin install-hooks` run via `sys.executable -m pezin` (after 3.2), `PATH` stripped of the venv bin, `feat:` commit succeeds, version bumped, changelog section ordered correctly, tag created.

## 5. Validation and release prep

- [x] 5.1 Run `ruff check --fix`, `ruff format`, `pytest`, `pytest -m slow`, and `openspec validate harden-hooks-and-changelog --strict`; resolve findings.
- [x] 5.2 Update `README.md` install-hooks section if it mentions the python3 requirement; add `[Unreleased]` note to project `CHANGELOG.md`.
- [x] 5.3 Commit via conventional commits and let pezin's own hooks bump to 0.9.0; verify `git show HEAD --stat` includes `CHANGELOG.md`, version files, and tag `v0.9.0` exists.
  - Done twice: the first release commit exposed the multi-line promotion
    truncation (dogfooding worked as designed); rewound the local-only tag,
    fixed promotion + link consolidation, re-released. Commit `20d89c8`,
    tag `v0.9.0`, followed by `fec401b` (uv.lock sync).

## 6. Follow-ups discovered during apply (dogfood release commit)

- [x] 6.1 Promotion must keep multi-line bullets intact: `split_unreleased_entries` attaches indented continuation lines to their entry; regression test with a multi-line bullet.
- [x] 6.2 Regenerate version-comparison links and emit them once at the bottom of the file; strip old link-definition lines from re-emitted sections; regression test for single definitions.
- [x] 6.3 Add `repo_url` to `ChangelogHookConfig` (top-level + per-service override), used by the hook with git-remote fallback; configure it in pezin's own `pyproject.toml` (the remote derivation mangles SSH host aliases).
