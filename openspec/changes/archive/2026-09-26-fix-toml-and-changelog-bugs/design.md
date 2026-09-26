# Design

## Context

Three defects surfaced in v0.9.0 when the post-commit hook bumped doodoo 0.75.0 →
0.76.0 (see proposal.md - Why; specs deltas for exact requirements):

1. `TomlFileHandler.write_version` (`src/pezin/core/handlers.py`) round-trips the
   whole TOML file through `tomli.load` + `tomli_w.dump`, which discards comments,
   formatting and comment-only tables. Two sibling writers have the same flaw:
   `write_toml_version` (`src/pezin/cli/commands.py`, used by manual CLI bumps) and
   the hook's `update_version` (`src/pezin/hooks/pre_commit.py`, used when
   `[tool.pezin]` version-file config drives the bump).
2. `ChangelogManager.update_changelog` (`src/pezin/core/changelog.py`) merges
   promoted `[Unreleased]` subsections only when the title equals a configured
   section title byte-for-byte, so hand-written titles like `### ⚠️ Breaking Changes`
   fall through to the "unknown" tail.
3. `split_unreleased_entries` drops blank lines inside multi-line entries
   (`elif line.strip() and entries`), gluing bullets to fenced code blocks.

Constraints: test-first for each fix; no behavior change for canonical changelog
titles; the post-commit auto-amend flow and the parked-patch data-loss guard stay
untouched; full suite green; CHANGELOG entry added.

## Goals / Non-Goals

**Goals:**

- A version bump rewrites exactly the version value in TOML files — nothing else.
- `[Unreleased]` promotion survives human variation in subsection titles and
  formatting.
- Every fix lands with a regression test written (and failing) first.

**Non-Goals:**

- No new CLI flags, config keys, or output-format changes.
- No general-purpose TOML editing API; no change to how versions are *parsed*.
- Not touching JSON/generic handlers (they already do targeted edits).

## Decisions

### 1. Use tomlkit for all TOML writes that touch user files

Replace the `tomli_w` dump in the three writers (`TomlFileHandler.write_version`,
`cli/commands.py:write_toml_version`, `hooks/pre_commit.py:update_version`) with
tomlkit: parse the file, walk to the target key (reusing the existing dotted-key
logic), assign the new version string, write back.

- Rationale: tomlkit is a round-trip-preserving TOML editor — comments, key order,
  whitespace, and empty/comment-only tables survive by construction. It is already
  in the dev environment (0.15.1) and is the standard tool for this job.
- Alternative considered: targeted regex/line edit of the found key. Rejected:
  nested tables, dotted keys, arrays-of-tables and repeated keys make a correct
  text-level edit its own parser; tomlkit already solved that.
- `tomli`/`tomli_w` remain for pure-data paths that never rewrite user files
  (config reads, dumps of pezin-generated data). Add `tomlkit>=0.12` to
  `[project.dependencies]`.
- The hook path matters most: it must keep working inside the
  `atomic_worktree_guard` and the parked-patch check — the write is a drop-in
  replacement of the dump call, so guard semantics are unchanged.

### 2. Normalize section titles for matching, keep emission order as-is

Add a private title-normalization helper in `changelog.py` used only to *match*
promoted subsection titles against configured section titles:

- casefold, collapse whitespace;
- strip emoji/symbols (Unicode `So`/`Sk` categories) and variation selector
  U+FE0F / zero-width joiner;
- naive English singular/plural folding per word: strip a trailing `es` when the
  stem ends in `s/x/z/ch/sh` (`fixes` → `fix`), else strip a trailing `s`
  (`changes` → `change`, `refactors` → `refactor`).

First configured section whose normalized title equals the normalized promoted
title wins; its entries merge under the *canonical* configured title with the
existing dedupe. Emission order stays exactly the current logic (configured
sections in config order, unknown titles after, in original order), so breaking
changes land first under the default config and canonical-title changelogs are
byte-identical to today.

- Alternative considered: an `inflect`-style proper stemmer. Rejected: new
  dependency for a tiny, closed comparison set; a wrong singular/plural fold at
  worst merges a near-identical title, never loses entries.

### 3. Preserve interior blank lines by appending, trimming at flush

In `split_unreleased_entries`, append blank lines while an entry is open
(`entries` non-empty), and strip *trailing* blank lines per entry in `_flush`.
Interior blanks (bullet → blank → indented fenced block / sub-paragraph) survive;
trailing blanks before the next bullet, heading, or section end are dropped, which
is the current behavior everywhere else.

- Alternative considered: look ahead before appending a blank. Rejected: the
  flush-time trim is simpler and gives the same result.

## Risks / Trade-offs

- [tomlkit round-trip normalizes something subtle (e.g., trailing newline)] →
  The regression test asserts the post-write diff is *exactly* the version line;
  any normalization shows up as a red test before merge.
- [Naive plural folding false-positives (`Settings` ≈ `Setting`)] → Only merges
  entries into an existing configured section; no data loss, and unknown titles
  still render. Acceptable.
- [Existing tests assert the old rewrite/merge output] → Run the full suite;
  update only assertions that encode the buggy behavior, keeping the
  canonical-title cases untouched to prove the compatibility guarantee.
- [New runtime dependency increases install footprint] → tomlkit is pure Python,
  already common in the ecosystem; justified by data-loss prevention.

## Migration Plan

Ship as the next patch release. No config or API changes; upgrade-in-place.
Rollback = downgrade; files already written correctly by the fix stay correct
(files mangled by v0.9.0 are restored from git history by affected users).

## Open Questions

None.
