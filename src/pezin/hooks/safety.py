"""Safety helpers guarding pezin hooks against pre-commit data loss.

When the `pre-commit <https://pre-commit.com>`_ framework runs hooks it
"parks" any unstaged working-tree changes into a patch file inside its cache
directory and resets the worktree to the index (``staged_files_only``).
After the hooks finish it re-applies that patch.  If a hook rewrote one of
the parked files in the meantime, the patch no longer applies, pre-commit
crashes, and the parked changes survive *only* in the cache patch file -
the user's unstaged work effectively disappears from the repo.

Pezin's post-commit hook rewrites version files and the changelog, so it is
a prime candidate for triggering exactly that failure.  The helpers here let
the hook detect parked changes that overlap the files it is about to write
and skip instead, plus an atomic guard that restores the worktree, index and
HEAD if pezin's own write path fails halfway.
"""

import contextlib
import json
import os
import re
import subprocess
import time
from collections.abc import Iterable, Iterator
from pathlib import Path
from typing import Dict, Optional, Set

from ..logging import get_logger

logger = get_logger()

# Marker file (inside .git/, so it never dirties the worktree) written by the
# prepare-commit-msg hook. Parked patches older than it belong to earlier
# commits or *other repositories* sharing the pre-commit cache and must not
# suppress this commit's bump.  pre-commit never deletes its patch files
# (not even after a successful restore), so the marker is what tells this
# commit's patch apart from the leftovers.  A false positive merely skips
# one bump; a missed one can lose unstaged work, hence the marker.
SINCE_FILE_NAME = "pezin_parked_patch_since"

# Lower bound used when the marker is missing (e.g. only pezin-post
# installed, no pezin-prepare).  Keep short: without the marker, recency
# alone must not mistake another repo's leftover patch for this commit's
# (see README "Unstaged Changes and the pre-commit Data-Loss Guard").
_FALLBACK_SINCE_SECONDS = 60.0

_PATCH_NAME_RE = re.compile(r"^patch\d+-\d+$")


def record_hook_start(repo_root: Path) -> None:
    """Best-effort: stamp the prepare-commit-msg start time into .git/."""
    try:
        git_dir = Path(
            subprocess.run(
                ["git", "rev-parse", "--git-dir"],
                cwd=repo_root,
                capture_output=True,
                text=True,
                check=True,
            ).stdout.strip()
        )
        if not git_dir.is_absolute():
            git_dir = repo_root / git_dir
        (git_dir / SINCE_FILE_NAME).write_text(json.dumps({"at": time.time()}))
    except Exception as e:  # pragma: no cover - best effort only
        logger.debug(f"Could not record hook start: {e}")


def take_hook_start(repo_root: Path) -> Optional[float]:
    """Read (and unlink) the prepare-commit-msg start stamp, if present."""
    try:
        git_dir = Path(
            subprocess.run(
                ["git", "rev-parse", "--git-dir"],
                cwd=repo_root,
                capture_output=True,
                text=True,
                check=True,
            ).stdout.strip()
        )
        if not git_dir.is_absolute():
            git_dir = repo_root / git_dir
        marker = git_dir / SINCE_FILE_NAME
        if not marker.exists():
            return None
        at = float(json.loads(marker.read_text()).get("at", 0.0))
        marker.unlink(missing_ok=True)
        return at
    except Exception as e:  # pragma: no cover - best effort only
        logger.debug(f"Could not read hook start: {e}")
        return None


# `git apply --numstat` lists only the *target* path of renames; the
# source path appears in the raw patch body as `rename from <path>`.
_RENAME_FROM_RE = re.compile(r"^(?:rename|copy) from (.+)$", re.MULTILINE)


def find_pre_commit_home() -> Optional[Path]:
    """Locate pre-commit's cache directory, mirroring its own resolution.

    pre-commit resolves its store as ``$PRE_COMMIT_HOME`` or
    ``$XDG_CACHE_HOME/pre-commit`` or ``~/.cache/pre-commit`` (see
    ``pre_commit.store._get_default_directory``).  The parked patch files
    are written directly into that directory.
    """
    home = os.environ.get("PRE_COMMIT_HOME")
    if not home:
        cache = os.environ.get("XDG_CACHE_HOME") or os.path.expanduser("~/.cache")
        home = os.path.join(cache, "pre-commit")
    path = Path(home)
    return path if path.is_dir() else None


def patch_touched_paths(patch_path: Path) -> Set[str]:
    """Return the repo-relative paths a patch file touches.

    Uses ``git apply --numstat`` so git itself handles quoting and binary
    files; rename/copy *source* paths are additionally recovered from the
    raw patch body.
    """
    result = subprocess.run(
        ["git", "apply", "--numstat", str(patch_path)],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        logger.debug(f"Could not numstat patch {patch_path}: {result.stderr.strip()}")
        return set()

    paths: Set[str] = set()
    for line in result.stdout.splitlines():
        # numstat lines are "<added>\t<removed>\t<path>"
        parts = line.split("\t")
        if len(parts) < 3:
            continue
        raw = "\t".join(parts[2:]).strip()
        if not raw:
            continue
        if raw.startswith('"') and raw.endswith('"'):
            raw = raw[1:-1]
        paths.add(raw)

    try:
        body = patch_path.read_text(errors="replace")
    except OSError as e:
        logger.debug(f"Could not read patch {patch_path}: {e}")
        return paths
    for match in _RENAME_FROM_RE.finditer(body):
        source = match.group(1).strip()
        if source.startswith('"') and source.endswith('"'):
            source = source[1:-1]
        paths.add(source)
    return paths


def _patch_is_live(patch_path: Path, repo_root: Path) -> bool:
    """Whether a parked patch would still apply to the current worktree.

    A patch parked for the current commit was diffed against the index; while
    hooks run the worktree equals the index, so a live patch applies cleanly.
    Stale leftovers from earlier commits generally do not.
    """
    result = subprocess.run(
        [
            "git",
            "apply",
            "--check",
            "--whitespace=nowarn",
            str(patch_path),
        ],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )
    return result.returncode == 0


def find_parked_patch_conflicts(
    repo_root: Path,
    target_files: Iterable[str],
    since: Optional[float] = None,
) -> Dict[str, Set[Path]]:
    """Detect parked unstaged changes that overlap ``target_files``.

    Returns a mapping of repo-relative target file to the set of live parked
    patch files touching it.  Empty when nothing overlaps (the common case),
    when not running under pre-commit (``PRE_COMMIT`` env var unset), or when
    no pre-commit cache directory exists.

    Only patches created *after* ``since`` (the prepare-commit-msg start
    stamp, see :func:`record_hook_start`) are considered: the pre-commit
    cache is shared by every repository on the machine and patch files are
    never deleted, so recency alone cannot tell this commit's parked patch
    apart from another repo's leftovers.  Without a stamp a short fallback
    window (:data:`_FALLBACK_SINCE_SECONDS`) is used - a parked patch older
    than that is not detected, which is why installing pezin-prepare
    alongside pezin-post is required.
    """
    if os.environ.get("PRE_COMMIT") != "1":
        return {}

    pre_commit_home = find_pre_commit_home()
    if pre_commit_home is None:
        return {}

    targets: Set[str] = set()
    for target in target_files:
        normalized = _normalize_repo_relative(target, repo_root)
        if normalized:
            targets.add(normalized)
    if not targets:
        return {}

    now = time.time()
    lower_bound = since - 1.0 if since is not None else now - _FALLBACK_SINCE_SECONDS

    conflicts: Dict[str, Set[Path]] = {}
    for candidate in pre_commit_home.iterdir():
        if not _PATCH_NAME_RE.match(candidate.name) or not candidate.is_file():
            continue
        try:
            mtime = candidate.stat().st_mtime
        except OSError:
            continue
        # Future timestamps (clock skew) are ignored, not trusted.
        if mtime > now or mtime < lower_bound:
            continue
        if not _patch_is_live(candidate, repo_root):
            continue
        overlap = patch_touched_paths(candidate) & targets
        for path in overlap:
            conflicts.setdefault(path, set()).add(candidate)

    if conflicts:
        logger.warning(f"Parked pre-commit patches overlap pezin targets: {conflicts}")
    return conflicts


@contextlib.contextmanager
def atomic_worktree_guard(repo_root: Path, files: Iterable[str]) -> Iterator[None]:
    """Restore the worktree, index and HEAD if the block fails.

    Snapshots the byte content of ``files`` (missing files are remembered as
    absent), the current index tree and HEAD.  If the wrapped block raises,
    everything is restored to the snapshot before the exception propagates:
    file contents are written back, files created by the block are deleted,
    the index is reset via ``git read-tree`` and an amended HEAD is moved
    back with ``git reset --soft``.  On success nothing happens.
    """
    snapshot: Dict[str, Optional[bytes]] = {}
    for target in files:
        normalized = _normalize_repo_relative(target, repo_root)
        if not normalized or normalized in snapshot:
            continue
        path = repo_root / normalized
        snapshot[normalized] = path.read_bytes() if path.exists() else None

    head_before = _git_text(repo_root, ["rev-parse", "HEAD"])
    tree_before = _git_text(repo_root, ["write-tree"])

    try:
        yield
    except BaseException:
        logger.warning("Bump failed - restoring worktree, index and HEAD")
        for rel, content in snapshot.items():
            path = repo_root / rel
            try:
                if content is None:
                    path.unlink(missing_ok=True)
                else:
                    path.write_bytes(content)
            except OSError as e:
                logger.error(f"Failed to restore {rel}: {e}")

        if tree_before:
            _git_best_effort(repo_root, ["read-tree", tree_before])
        if head_before and tree_before:
            head_now = _git_text(repo_root, ["rev-parse", "HEAD"])
            if head_now and head_now != head_before:
                _git_best_effort(repo_root, ["reset", "--soft", head_before])
        raise


def _normalize_repo_relative(path: str, repo_root: Path) -> Optional[str]:
    """Normalize any configured path to a repo-relative posix path."""
    candidate = Path(path)
    if not candidate.is_absolute():
        candidate = repo_root / candidate
    try:
        resolved_root = repo_root.resolve()
        rel = candidate.resolve().relative_to(resolved_root)
    except (OSError, ValueError):
        return None
    normalized = rel.as_posix()
    return normalized if normalized not in (".", "") else None


def _git_text(repo_root: Path, args: list) -> Optional[str]:
    """Run a git command, returning stripped stdout or None on failure."""
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()
    except (subprocess.CalledProcessError, OSError) as e:
        logger.debug(f"git {' '.join(args)} failed: {e}")
        return None


def _git_best_effort(repo_root: Path, args: list) -> bool:
    """Run a git command, logging failures without raising."""
    try:
        subprocess.run(
            ["git", *args],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=True,
        )
        return True
    except (subprocess.CalledProcessError, OSError) as e:
        logger.error(f"git {' '.join(args)} failed: {e}")
        return False
