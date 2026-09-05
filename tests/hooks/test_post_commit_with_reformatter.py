"""End-to-end regression tests for the post-commit hook.

Each test spins up a real `pre-commit` installation against a throwaway
git repo to exercise the stash/restore + amend interaction that motivated
moving pezin off the commit-msg stage. Tagged `slow`; opt in with
`pytest -m slow tests/hooks/`.
"""

import subprocess
from pathlib import Path

import pytest

from .conftest import hook_env

pytestmark = pytest.mark.slow


def _write_pyproject(repo: Path, version: str = "0.0.0") -> None:
    (repo / "pyproject.toml").write_text(
        f'[project]\nname = "demo"\nversion = "{version}"\n'
    )


def _seed_initial_commit(repo: Path) -> None:
    """Initial chore commit so HEAD exists; pezin hooks are bypassed."""
    env = hook_env()
    subprocess.run(["git", "add", "pyproject.toml"], cwd=repo, check=True, env=env)
    subprocess.run(
        ["git", "commit", "-m", "chore: init", "--no-verify"],
        cwd=repo,
        check=True,
        capture_output=True,
        env=env,
    )


def _git_commit(repo: Path, message: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "commit", "-m", message],
        cwd=repo,
        capture_output=True,
        text=True,
        env=hook_env(),
    )


def _show_head_stat(repo: Path) -> str:
    return subprocess.run(
        ["git", "show", "HEAD", "--stat"],
        cwd=repo,
        capture_output=True,
        text=True,
        check=True,
        env=hook_env(),
    ).stdout


def _status_porcelain(repo: Path) -> str:
    return subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=repo,
        capture_output=True,
        text=True,
        check=True,
        env=hook_env(),
    ).stdout


def test_feat_commit_lands_version_and_changelog(
    tmp_git_repo: Path, install_reformatter_hook
):
    """Scenarios 1 + 3: reformatter retry, then assert version + CHANGELOG.

    First commit attempt is aborted by the reformatter (file rewritten,
    exit 1). Test re-stages and retries. HEAD must contain the source
    file, pyproject.toml, and CHANGELOG.md; the new section must include
    the commit summary under Features.
    """
    repo = tmp_git_repo
    _write_pyproject(repo, version="0.0.0")
    _seed_initial_commit(repo)
    install_reformatter_hook(repo)

    src = repo / "feature.py"
    src.write_text("print('thing')")  # No trailing newline — reformatter fails first
    subprocess.run(["git", "add", "feature.py"], cwd=repo, check=True, env=hook_env())

    first = _git_commit(repo, "feat: add thing")
    assert first.returncode != 0, (
        "Reformatter should have aborted the first attempt; "
        f"stdout={first.stdout!r} stderr={first.stderr!r}"
    )

    # Re-stage the reformatted file and retry.
    subprocess.run(["git", "add", "feature.py"], cwd=repo, check=True, env=hook_env())
    second = _git_commit(repo, "feat: add thing")
    assert second.returncode == 0, (
        f"Second attempt should pass; stdout={second.stdout!r} stderr={second.stderr!r}"
    )

    stat = _show_head_stat(repo)
    assert "feature.py" in stat
    assert "pyproject.toml" in stat
    assert "CHANGELOG.md" in stat

    # The scenario clause "git status --porcelain is empty after the commit
    # completes" guards against the prior bug class — a leaked bump or stale
    # lock file. Untracked test-scaffolding (.pre-commit-config.yaml,
    # reformatter.py) is expected here, so filter the `??` lines out.
    tracked_residue = [
        line
        for line in _status_porcelain(repo).splitlines()
        if not line.startswith("??")
    ]
    assert tracked_residue == [], (
        f"Tracked files left modified after commit: {tracked_residue}"
    )
    assert not (repo / ".pezin_post_commit_lock").exists()
    assert not (repo / ".pezin_skip_version_bump").exists()

    changelog = (repo / "CHANGELOG.md").read_text()
    assert "## [0.1.0]" in changelog
    assert "add thing" in changelog
    features_idx = changelog.find("Features")
    add_thing_idx = changelog.find("add thing")
    assert features_idx != -1 and features_idx < add_thing_idx, (
        "`add thing` should appear under the Features heading"
    )

    pyproject = (repo / "pyproject.toml").read_text()
    assert 'version = "0.1.0"' in pyproject


def test_next_test_commit_does_not_inherit_bump(
    tmp_git_repo: Path, install_reformatter_hook
):
    """Scenario 2: a subsequent `test:` commit must not include the prior bump."""
    repo = tmp_git_repo
    _write_pyproject(repo, version="0.0.0")
    _seed_initial_commit(repo)
    install_reformatter_hook(repo)

    # First do a feat commit so a bump exists.
    (repo / "feature.py").write_text("print('thing')\n")
    subprocess.run(["git", "add", "feature.py"], cwd=repo, check=True, env=hook_env())
    feat = _git_commit(repo, "feat: add thing")
    assert feat.returncode == 0, (
        f"feat commit failed; stdout={feat.stdout!r} stderr={feat.stderr!r}"
    )

    # Now a test: commit with only a new test file. No bump expected.
    (repo / "test_feature.py").write_text("def test_thing():\n    pass\n")
    subprocess.run(
        ["git", "add", "test_feature.py"], cwd=repo, check=True, env=hook_env()
    )
    test_commit = _git_commit(repo, "test: add coverage")
    assert test_commit.returncode == 0, (
        f"test commit failed; stdout={test_commit.stdout!r} "
        f"stderr={test_commit.stderr!r}"
    )

    stat = _show_head_stat(repo)
    assert "test_feature.py" in stat
    assert "pyproject.toml" not in stat
    assert "CHANGELOG.md" not in stat

    pyproject = (repo / "pyproject.toml").read_text()
    assert 'version = "0.1.0"' in pyproject, (
        "pyproject.toml should remain at the prior bumped version"
    )
