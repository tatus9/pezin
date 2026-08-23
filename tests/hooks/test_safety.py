"""Unit tests for pezin.hooks.safety (parked-patch detection + rollback)."""

import subprocess
import time
from pathlib import Path

import pytest

from pezin.hooks.safety import (
    atomic_worktree_guard,
    find_parked_patch_conflicts,
    find_pre_commit_home,
    patch_touched_paths,
    record_hook_start,
    take_hook_start,
)


@pytest.fixture
def git_repo(tmp_path: Path) -> Path:
    """Minimal git repo with one tracked file."""
    repo = tmp_path / "repo"
    repo.mkdir()
    env = {
        "PATH": "/usr/bin:/bin",
        "GIT_AUTHOR_NAME": "T",
        "GIT_AUTHOR_EMAIL": "t@e.com",
        "GIT_COMMITTER_NAME": "T",
        "GIT_COMMITTER_EMAIL": "t@e.com",
        "GIT_CONFIG_GLOBAL": "/dev/null",
        "GIT_CONFIG_SYSTEM": "/dev/null",
    }
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=repo, check=True, env=env)
    subprocess.run(
        ["git", "config", "user.email", "t@e.com"], cwd=repo, check=True, env=env
    )
    subprocess.run(["git", "config", "user.name", "T"], cwd=repo, check=True, env=env)
    (repo / "package.json").write_text('{\n  "version": "0.1.0"\n}\n')
    (repo / "other.txt").write_text("seed\n")
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, env=env)
    subprocess.run(["git", "commit", "-q", "-m", "init"], cwd=repo, check=True, env=env)
    return repo


def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args], cwd=repo, capture_output=True, text=True, check=True
    )
    return result.stdout


class TestFindPreCommitHome:
    def test_prefers_pre_commit_home_env(self, tmp_path, monkeypatch):
        home = tmp_path / "pc-home"
        home.mkdir()
        monkeypatch.setenv("PRE_COMMIT_HOME", str(home))
        assert find_pre_commit_home() == home

    def test_falls_back_to_xdg_cache_home(self, tmp_path, monkeypatch):
        cache = tmp_path / "cache"
        (cache / "pre-commit").mkdir(parents=True)
        monkeypatch.delenv("PRE_COMMIT_HOME", raising=False)
        monkeypatch.setenv("XDG_CACHE_HOME", str(cache))
        assert find_pre_commit_home() == cache / "pre-commit"

    def test_missing_directory_returns_none(self, tmp_path, monkeypatch):
        monkeypatch.setenv("PRE_COMMIT_HOME", str(tmp_path / "does-not-exist"))
        assert find_pre_commit_home() is None


class TestPatchTouchedPaths:
    def test_parses_regular_and_rename_entries(self, git_repo, tmp_path):
        # Modify one file, rename another (staged) -> diff HEAD shows both
        (git_repo / "other.txt").write_text("modified\n")
        _git(git_repo, "mv", "package.json", "renamed.json")
        patch = tmp_path / "patch123-1"
        patch.write_text(_git(git_repo, "diff", "HEAD", "--binary"))

        touched = patch_touched_paths(patch)
        assert touched == {"other.txt", "package.json", "renamed.json"}

    def test_garbage_patch_returns_empty(self, tmp_path):
        patch = tmp_path / "patch123-2"
        patch.write_text("not a patch at all\n")
        assert patch_touched_paths(patch) == set()


def _write_patch(dest: Path, content: str) -> Path:
    dest.write_text(content)
    return dest


def _simple_patch(repo: Path, new_content: str) -> str:
    """Diff of other.txt from seed to new_content, repo-relative."""
    old = (repo / "other.txt").read_text()
    return (
        f"diff --git a/other.txt b/other.txt\n"
        f"index 1234567..89abcde 100644\n"
        f"--- a/other.txt\n"
        f"+++ b/other.txt\n"
        f"@@ -1 +1 @@\n"
        f"-{old.rstrip(chr(10))}\n"
        f"+{new_content}\n"
    )


class TestFindParkedPatchConflicts:
    def _setup(self, git_repo, tmp_path, monkeypatch):
        pc_home = tmp_path / "pc-home"
        pc_home.mkdir()
        monkeypatch.setenv("PRE_COMMIT", "1")
        monkeypatch.setenv("PRE_COMMIT_HOME", str(pc_home))
        return pc_home

    def test_not_under_pre_commit_returns_empty(self, git_repo, tmp_path, monkeypatch):
        pc_home = self._setup(git_repo, tmp_path, monkeypatch)
        monkeypatch.delenv("PRE_COMMIT", raising=False)
        _write_patch(pc_home / "patch100-1", _simple_patch(git_repo, "x"))
        assert find_parked_patch_conflicts(git_repo, {"other.txt"}) == {}

    def test_live_patch_touching_target_conflicts(
        self, git_repo, tmp_path, monkeypatch
    ):
        pc_home = self._setup(git_repo, tmp_path, monkeypatch)
        patch = _write_patch(pc_home / "patch100-2", _simple_patch(git_repo, "x"))

        conflicts = find_parked_patch_conflicts(
            git_repo, {"other.txt", "elsewhere.txt"}
        )
        assert conflicts == {"other.txt": {patch}}

    def test_patch_touching_other_files_is_ignored(
        self, git_repo, tmp_path, monkeypatch
    ):
        pc_home = self._setup(git_repo, tmp_path, monkeypatch)
        _write_patch(pc_home / "patch100-3", _simple_patch(git_repo, "x"))

        assert find_parked_patch_conflicts(git_repo, {"package.json"}) == {}

    def test_stale_patch_by_age_is_ignored(self, git_repo, tmp_path, monkeypatch):
        pc_home = self._setup(git_repo, tmp_path, monkeypatch)
        patch = _write_patch(pc_home / "patch100-4", _simple_patch(git_repo, "x"))
        old = time.time() - 3600
        import os

        os.utime(patch, (old, old))

        assert find_parked_patch_conflicts(git_repo, {"other.txt"}) == {}

    def test_patch_that_no_longer_applies_is_ignored(
        self, git_repo, tmp_path, monkeypatch
    ):
        pc_home = self._setup(git_repo, tmp_path, monkeypatch)
        # Patch made against content that has since changed on disk
        _write_patch(pc_home / "patch100-5", _simple_patch(git_repo, "x"))
        (git_repo / "other.txt").write_text("already changed\n")

        assert find_parked_patch_conflicts(git_repo, {"other.txt"}) == {}

    def test_non_patch_files_are_ignored(self, git_repo, tmp_path, monkeypatch):
        pc_home = self._setup(git_repo, tmp_path, monkeypatch)
        _write_patch(pc_home / "notapatch.txt", _simple_patch(git_repo, "x"))

        assert find_parked_patch_conflicts(git_repo, {"other.txt"}) == {}


class TestHookStartMarker:
    def test_roundtrip_and_unlink(self, git_repo):
        record_hook_start(git_repo)
        stamp = take_hook_start(git_repo)
        assert stamp is not None and abs(stamp - time.time()) < 30
        # consumed on read
        assert take_hook_start(git_repo) is None

    def test_marker_stays_out_of_worktree(self, git_repo):
        record_hook_start(git_repo)
        assert _git(git_repo, "status", "--porcelain").strip() == ""


class TestSinceBound:
    def test_patch_older_than_since_is_ignored(self, git_repo, tmp_path, monkeypatch):
        """Leftover patches from other repos must not suppress the bump."""
        pc_home = tmp_path / "pc-home"
        pc_home.mkdir()
        monkeypatch.setenv("PRE_COMMIT", "1")
        monkeypatch.setenv("PRE_COMMIT_HOME", str(pc_home))
        _write_patch(pc_home / "patch100-6", _simple_patch(git_repo, "x"))

        since = time.time() + 60  # marker stamped *after* the patch was parked
        assert find_parked_patch_conflicts(git_repo, {"other.txt"}, since=since) == {}

    def test_patch_newer_than_since_conflicts(self, git_repo, tmp_path, monkeypatch):
        pc_home = tmp_path / "pc-home"
        pc_home.mkdir()
        monkeypatch.setenv("PRE_COMMIT", "1")
        monkeypatch.setenv("PRE_COMMIT_HOME", str(pc_home))
        patch = _write_patch(pc_home / "patch100-7", _simple_patch(git_repo, "x"))

        since = time.time() - 60
        conflicts = find_parked_patch_conflicts(git_repo, {"other.txt"}, since=since)
        assert conflicts == {"other.txt": {patch}}


class TestAtomicWorktreeGuard:
    def test_restores_files_index_and_created_files_on_failure(self, git_repo):
        original = (git_repo / "package.json").read_text()
        head_before = _git(git_repo, "rev-parse", "HEAD").strip()

        with pytest.raises(RuntimeError):
            with atomic_worktree_guard(git_repo, ["package.json", "CHANGELOG.md"]):
                (git_repo / "package.json").write_text('{"version": "9.9.9"}')
                (git_repo / "CHANGELOG.md").write_text("created")
                _git(git_repo, "add", "-A")
                raise RuntimeError("boom")

        assert (git_repo / "package.json").read_text() == original
        assert not (git_repo / "CHANGELOG.md").exists()
        # index restored: no staged changes remain
        status = _git(git_repo, "status", "--porcelain")
        assert status.strip() == ""
        # HEAD untouched
        assert _git(git_repo, "rev-parse", "HEAD").strip() == head_before

    def test_nothing_restored_on_success(self, git_repo):
        original = (git_repo / "package.json").read_text()
        with atomic_worktree_guard(git_repo, ["package.json"]):
            pass
        assert (git_repo / "package.json").read_text() == original


class TestCollectWriteTargets:
    """Unit tests for the target-collection used by the parked-patch guard."""

    def test_no_config_falls_back_to_found_config_file(self, git_repo):
        from pezin.hooks.post_commit import _collect_write_targets

        # Plain JS project: no pezin config, package.json found by fallback.
        # (Paths are normalized to repo-relative later, inside the guard.)
        targets = _collect_write_targets({}, git_repo, git_repo / "package.json")
        assert targets == {
            str(git_repo / "package.json"),
            str(git_repo / "CHANGELOG.md"),
        }

    def test_no_config_and_no_config_file_yields_changelog_only(self, git_repo):
        from pezin.hooks.post_commit import _collect_write_targets

        targets = _collect_write_targets({}, git_repo)
        assert targets == {str(git_repo / "CHANGELOG.md")}

    def test_explicit_config_lists_version_files_and_changelog(self, git_repo):
        from pezin.hooks.post_commit import _collect_write_targets

        pezin_config = {
            "version_files": [{"path": str(git_repo / "package.json")}],
        }
        targets = _collect_write_targets(pezin_config, git_repo)
        assert targets == {
            str(git_repo / "package.json"),
            str(git_repo / "CHANGELOG.md"),
        }

    def test_disabled_changelog_excluded(self, git_repo):
        from pezin.hooks.post_commit import _collect_write_targets

        pezin_config = {
            "version_files": [{"path": str(git_repo / "package.json")}],
            "changelog": {"enabled": False},
        }
        targets = _collect_write_targets(pezin_config, git_repo)
        assert targets == {str(git_repo / "package.json")}


class TestSelfRepoVersionFilePattern:
    """Pin the regex pair pezin itself uses for src/pezin/__init__.py."""

    def test_init_py_pattern_reads_and_writes(self, tmp_path):
        from pezin.core.version import VersionManager, VersionFileConfig
        from pezin.core.version import Version

        init = tmp_path / "__init__.py"
        init.write_text(
            'from .core import thing\n\n__version__ = "0.8.2"\n\n__all__ = []\n'
        )
        vm = VersionManager(
            [
                VersionFileConfig(
                    path=str(init),
                    version_pattern=r'__version__\s*=\s*"([^"]+)"',
                    version_replacement=r'__version__ = "{version}"',
                )
            ]
        )
        parsed = vm.get_primary_version()
        assert parsed is not None and str(parsed) == "0.8.2"
        vm.write_versions(Version("0.9.0"))
        assert '__version__ = "0.9.0"' in init.read_text()
