"""End-to-end regression tests for the pre-commit parked-patch data loss.

Reproduces the 2026-08-23 viniline incident: a commit whose unstaged changes
touched a file pezin rewrites (package.json) used to make pre-commit's
parked-patch restore fail, wiping the unstaged work from the worktree.
The fix detects the parked patch and skips the bump instead.

Tagged `slow` (real git + pre-commit subprocesses); opt in with
`pytest -m slow tests/hooks/`.
"""

import json
import subprocess
from pathlib import Path

import pytest

from .conftest import PY, hook_env

pytestmark = pytest.mark.slow


def _git(repo: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args],
        cwd=repo,
        capture_output=True,
        text=True,
        check=check,
        env=hook_env(),
    )


def _seed_json_repo(repo: Path, version: str = "0.1.0") -> None:
    """Seed a repo versioned through package.json (as the consumer repo)."""
    (repo / "package.json").write_text(
        json.dumps({"name": "demo", "version": version, "deps": {}}, indent=2) + "\n"
    )
    (repo / "notes.txt").write_text("seed\n")
    (repo / "pyproject.toml").write_text(
        '[tool.pezin]\nversion_files = [{path = "package.json", file_type = "json"}]\n'
    )
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "chore: init", "--no-verify")


def _version(repo: Path, ref: str = "") -> str:
    """Current version: worktree when no ref, else the blob at `ref`."""
    if ref:
        out = _git(repo, "show", f"{ref}:package.json").stdout
    else:
        out = (repo / "package.json").read_text()
    return json.loads(out)["version"]


def test_unstaged_version_file_never_loses_work(
    tmp_git_repo: Path, install_pezin_hooks
):
    """The data-loss repro: parked unstaged edits to package.json.

    Previously pezin bumped package.json, pre-commit's parked-patch restore
    failed ("patch does not apply"), and the unstaged work vanished from the
    worktree. Now the bump is skipped and every unstaged byte survives.
    """
    repo = tmp_git_repo
    _seed_json_repo(repo, version="0.62.5")
    install_pezin_hooks(repo)

    (repo / "feature.py").write_text("print('thing')\n")
    _git(repo, "add", "feature.py")

    # Unstaged work: package.json (a pezin target) plus an unrelated file
    package = json.loads((repo / "package.json").read_text())
    package["deps"]["user-unstaged-key"] = "yes"
    (repo / "package.json").write_text(json.dumps(package, indent=2) + "\n")
    (repo / "notes.txt").write_text("IMPORTANT UNSTAGED WORK\n")
    unstaged_package = (repo / "package.json").read_text()

    commit = _git(repo, "commit", "-m", "feat: add thing", check=False)

    assert commit.returncode == 0, (
        f"commit failed: stdout={commit.stdout!r} stderr={commit.stderr!r}"
    )
    # The data-loss guarantee: unstaged bytes survive the commit untouched.
    assert (repo / "package.json").read_text() == unstaged_package
    assert (repo / "notes.txt").read_text() == "IMPORTANT UNSTAGED WORK\n"
    # The bump was skipped, not collided with.
    assert _version(repo) == "0.62.5"
    assert _version(repo, "HEAD") == "0.62.5"
    assert _git(repo, "tag").stdout.strip() == ""


def test_unstaged_other_files_still_bump(tmp_git_repo: Path, install_pezin_hooks):
    """Unstaged work outside pezin's write targets must not block the bump."""
    repo = tmp_git_repo
    _seed_json_repo(repo, version="0.1.0")
    install_pezin_hooks(repo)

    (repo / "feature.py").write_text("print('thing')\n")
    _git(repo, "add", "feature.py")
    (repo / "notes.txt").write_text("IMPORTANT UNSTAGED WORK\n")

    commit = _git(repo, "commit", "-m", "feat: add thing", check=False)

    assert commit.returncode == 0, (
        f"commit failed: stdout={commit.stdout!r} stderr={commit.stderr!r}"
    )
    # Bump + tag landed (happy path preserved)...
    assert _version(repo) == "0.2.0"
    assert _version(repo, "HEAD") == "0.2.0"
    assert "v0.2.0" in _git(repo, "tag").stdout
    # ...and the unrelated unstaged work survived the parked-patch roundtrip.
    assert (repo / "notes.txt").read_text() == "IMPORTANT UNSTAGED WORK\n"


def test_failed_amend_restores_worktree_and_index(tmp_git_repo: Path):
    """Failure-path guarantee: a hook crash must leave no residue.

    The amend inside the post-commit hook is forced to fail (ssh signing
    with a nonexistent key). The atomic guard must restore the worktree,
    index and HEAD byte-identically - no half-applied bump, no leftover
    CHANGELOG.md.
    """
    repo = tmp_git_repo
    _seed_json_repo(repo, version="0.1.0")

    (repo / "feature.py").write_text("print('thing')\n")
    _git(repo, "add", "feature.py")
    _git(repo, "commit", "-m", "feat: add thing", "--no-verify")

    head_before = _git(repo, "rev-parse", "HEAD").stdout.strip()
    package_before = (repo / "package.json").read_text()

    # Make `git commit --amend` fail deterministically inside the hook.
    _git(repo, "config", "commit.gpgsign", "true")
    _git(repo, "config", "gpg.format", "ssh")
    _git(repo, "config", "user.signingkey", "/nonexistent/signing-key")

    hook = subprocess.run(
        [PY, "-m", "pezin.hooks.post_commit"],
        cwd=repo,
        capture_output=True,
        text=True,
        env=hook_env(),
    )

    assert hook.returncode == 0, (
        f"hook should exit cleanly after rollback: "
        f"stdout={hook.stdout!r} stderr={hook.stderr!r}"
    )
    assert _git(repo, "rev-parse", "HEAD").stdout.strip() == head_before
    assert (repo / "package.json").read_text() == package_before
    assert not (repo / "CHANGELOG.md").exists()
    assert _git(repo, "status", "--porcelain").stdout.strip() == ""
    assert _git(repo, "tag").stdout.strip() == ""
