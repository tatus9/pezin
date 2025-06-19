"""Tests for the pre-commit hook."""

import subprocess
from pathlib import Path

import tomli
import tomli_w
from typer.testing import CliRunner

# from pumper.hooks.pre_commit import app
from pumper.cli.main import app
from pumper.hooks.pre_commit import is_amend_commit


def test_pre_commit_hook_installation(pre_commit_repo):
    """Test that pre-commit hook can be installed."""
    subprocess.run(
        ["pre-commit", "install", "--hook-type", "commit-msg"],
        cwd=pre_commit_repo,
        check=True,
    )
    hook_path = pre_commit_repo / ".git/hooks/commit-msg"
    assert hook_path.exists()


def test_simple_version_bump(tmp_path):
    """Test basic version bump functionality."""
    # Setup
    msg_file = tmp_path / "commit-msg"
    version_file = tmp_path / "pyproject.toml"

    # Create version file
    with open(version_file, "wb") as f:
        tomli_w.dump({"project": {"version": "0.1.0"}}, f)

    # Test feature bump
    msg_file.write_text("feat: add new feature")

    # Run hook with explicit config pointing to our test file
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "hook",
            str(msg_file),
            "--config",
            str(version_file),
            "--skip-amend-detection",
        ],
    )
    assert result.exit_code == 0, f"Hook failed: {result.stdout}"

    # Verify version bump
    with open(version_file, "rb") as f:
        version = tomli.load(f)["project"]["version"]
        assert version == "0.2.0"


def test_no_version_bump(tmp_path):
    """Test no bump for chore commits."""
    # Setup files
    msg_file = tmp_path / "commit-msg"
    version_file = tmp_path / "pyproject.toml"

    # Create version file
    with open(version_file, "wb") as f:
        tomli_w.dump({"project": {"version": "0.1.0"}}, f)

    # Write chore commit
    msg_file.write_text("chore: update docs")

    # Run hook with explicit config pointing to our test file
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "hook",
            str(msg_file),
            "--config",
            str(version_file),
            "--skip-amend-detection",
        ],
    )
    assert result.exit_code == 0, (
        f"Hook should succeed for chore commit: {result.stdout}"
    )
    assert "No version bump needed" in result.stdout

    # Version should not change
    with open(version_file, "rb") as f:
        version = tomli.load(f)["project"]["version"]
        assert version == "0.1.0"


def test_prerelease_bump(tmp_path):
    """Test pre-release version bump."""
    # Setup files
    msg_file = tmp_path / "commit-msg"
    version_file = tmp_path / "pyproject.toml"

    # Create version file
    with open(version_file, "wb") as f:
        tomli_w.dump({"project": {"version": "0.1.0"}}, f)

    # Write pre-release commit
    msg_file.write_text("feat: alpha feature\n\n[pre-release=alpha]")

    # Run hook with explicit config pointing to our test file
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "hook",
            str(msg_file),
            "--config",
            str(version_file),
            "--skip-amend-detection",
        ],
    )
    assert result.exit_code == 0

    # Check version has alpha tag
    with open(version_file, "rb") as f:
        version = tomli.load(f)["project"]["version"]
        assert "-alpha" in version


def test_amend_commit_detection(tmp_path):
    """Test amend commit detection functionality."""
    # Create a git repository
    git_repo = tmp_path / "test_repo"
    git_repo.mkdir()

    # Initialize git repo
    subprocess.run(["git", "init"], cwd=git_repo, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.name", "Test User"], cwd=git_repo, check=True
    )
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"], cwd=git_repo, check=True
    )

    # Create a test file and make initial commit
    test_file = git_repo / "test.txt"
    test_file.write_text("initial content")
    subprocess.run(["git", "add", "test.txt"], cwd=git_repo, check=True)
    subprocess.run(
        ["git", "commit", "-m", "feat: initial commit"], cwd=git_repo, check=True
    )

    # Change to the git repo directory for testing
    original_cwd = Path.cwd()
    try:
        import os

        os.chdir(git_repo)

        # Test 1: Different message should not be detected as amend
        different_message = "feat: different feature"
        assert not is_amend_commit(commit_message=different_message)

        # Test 2: Same message as HEAD should be detected as amend
        head_message = "feat: initial commit"
        assert is_amend_commit(commit_message=head_message)

        # Test 3: Test prepare-commit-msg detection - amend case
        assert is_amend_commit(commit_source="commit", commit_sha="abc123")

        # Test 4: Test prepare-commit-msg detection - normal commit case
        assert not is_amend_commit(commit_source="message")

        # Test 5: Test prepare-commit-msg detection - no arguments (fallback)
        assert not is_amend_commit()

        # Test 3: Empty repository case (create new repo)
        empty_repo = tmp_path / "empty_repo"
        empty_repo.mkdir()
        subprocess.run(["git", "init"], cwd=empty_repo, check=True, capture_output=True)
        subprocess.run(
            ["git", "config", "user.name", "Test User"], cwd=empty_repo, check=True
        )
        subprocess.run(
            ["git", "config", "user.email", "test@example.com"],
            cwd=empty_repo,
            check=True,
        )

        os.chdir(empty_repo)
        # No HEAD exists, should not be amend
        assert not is_amend_commit(commit_message="feat: first commit")

    finally:
        os.chdir(original_cwd)


def test_hook_skips_amend_commit(tmp_path):
    """Test that the hook skips version bumping for amend commits."""
    # Create git repository
    git_repo = tmp_path / "test_repo"
    git_repo.mkdir()

    # Setup git repo
    subprocess.run(["git", "init"], cwd=git_repo, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.name", "Test User"], cwd=git_repo, check=True
    )
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"], cwd=git_repo, check=True
    )

    # Create version file
    version_file = git_repo / "pyproject.toml"
    with open(version_file, "wb") as f:
        tomli_w.dump({"project": {"version": "1.0.0"}}, f)

    # Add and commit version file
    subprocess.run(["git", "add", "pyproject.toml"], cwd=git_repo, check=True)
    subprocess.run(
        ["git", "commit", "-m", "feat: add version file"], cwd=git_repo, check=True
    )

    # Create commit message file with same message as HEAD (simulating amend)
    msg_file = git_repo / "commit-msg"
    msg_file.write_text("feat: add version file")

    # Run hook from the git repo directory
    original_cwd = Path.cwd()
    try:
        import os

        os.chdir(git_repo)

        runner = CliRunner()
        result = runner.invoke(app, ["hook", str(msg_file)])

        # Hook should exit successfully but skip version bump
        assert result.exit_code == 0
        assert "Amend commit detected - skipping version bump" in result.stdout

        # Version should remain unchanged
        with open(version_file, "rb") as f:
            version = tomli.load(f)["project"]["version"]
            assert version == "1.0.0"  # Should not have changed

    finally:
        os.chdir(original_cwd)


def test_orig_head_amend_detection(tmp_path):
    """Test ORIG_HEAD based amend detection."""
    import os

    # Create git repository
    git_repo = tmp_path / "test_repo"
    git_repo.mkdir()

    # Setup git repo
    subprocess.run(["git", "init"], cwd=git_repo, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.name", "Test User"], cwd=git_repo, check=True
    )
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"], cwd=git_repo, check=True
    )

    # Create and commit initial file
    test_file = git_repo / "test.txt"
    test_file.write_text("initial")
    subprocess.run(["git", "add", "test.txt"], cwd=git_repo, check=True)
    subprocess.run(
        ["git", "commit", "-m", "feat: initial commit"], cwd=git_repo, check=True
    )

    original_cwd = Path.cwd()
    try:
        os.chdir(git_repo)

        # Test without ORIG_HEAD (normal case)
        assert not is_amend_commit("feat: new feature")

        # Simulate ORIG_HEAD existence (manually create it as Git would during amend)
        git_dir_result = subprocess.run(
            ["git", "rev-parse", "--git-dir"],
            capture_output=True,
            text=True,
            check=True,
        )
        git_dir = Path(git_dir_result.stdout.strip())
        orig_head_file = git_dir / "ORIG_HEAD"

        # Write current HEAD to ORIG_HEAD (as Git does during amend)
        head_result = subprocess.run(
            ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True
        )
        orig_head_file.write_text(head_result.stdout.strip())

        # Now it should detect as amend
        assert is_amend_commit("feat: any message")

        # Clean up
        orig_head_file.unlink()

    finally:
        os.chdir(original_cwd)
