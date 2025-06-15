import pytest
from pathlib import Path
import tempfile
import subprocess
from typing import Generator, Tuple


@pytest.fixture
def git_repo() -> Generator[Tuple[Path, subprocess.Popen], None, None]:
    """Create a temporary git repository for testing.

    This fixture:
    1. Creates a temporary directory
    2. Initializes a git repository
    3. Sets up basic git config
    4. Creates an initial commit

    Yields:
        Tuple containing:
        - Path to repo directory
        - subprocess.Popen object for the git daemon
    """
    with tempfile.TemporaryDirectory() as temp_dir:
        repo_dir = Path(temp_dir)

        # Initialize git repo
        subprocess.run(["git", "init"], cwd=repo_dir, check=True)

        # Configure git
        subprocess.run(
            ["git", "config", "user.email", "test@example.com"],
            cwd=repo_dir,
            check=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Test User"], cwd=repo_dir, check=True
        )

        # Create initial files
        pyproject = repo_dir / "pyproject.toml"
        pyproject.write_text("""[project]
name = "test-project"
version = "0.1.0"
""")

        readme = repo_dir / "README.md"
        readme.write_text("# Test Project\n")

        changelog = repo_dir / "CHANGELOG.md"
        changelog.write_text("""# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]
""")

        # Initial commit
        subprocess.run(["git", "add", "."], cwd=repo_dir, check=True)
        subprocess.run(
            ["git", "commit", "-m", "chore: initial commit"], cwd=repo_dir, check=True
        )

        # Start git daemon for local operations
        daemon = subprocess.Popen(
            ["git", "daemon", "--reuseaddr", "--base-path=.", "--export-all", "."],
            cwd=repo_dir,
        )

        yield repo_dir, daemon

        # Cleanup
        daemon.terminate()
        daemon.wait()


@pytest.fixture
def pre_commit_repo(git_repo: Tuple[Path, subprocess.Popen]) -> Path:
    """Create a git repository with pre-commit hook configured.

    This fixture extends git_repo by:
    1. Installing pre-commit
    2. Creating .pre-commit-config.yaml
    3. Installing hooks

    Returns:
        Path to repository directory
    """
    repo_dir, _ = git_repo

    # Create pre-commit config
    config = repo_dir / ".pre-commit-config.yaml"
    config.write_text("""repos:
-   repo: local
    hooks:
    -   id: pumper
        name: Pumper Version Control
        entry: pumper bump patch
        language: python
        pass_filenames: false
""")

    # Install pre-commit
    subprocess.run(
        ["pre-commit", "install"], cwd=repo_dir, check=True, capture_output=True
    )

    return repo_dir


@pytest.fixture
def temp_workspace(tmp_path: Path) -> Path:
    """Create a temporary workspace with basic project structure.

    Returns:
        Path to workspace directory
    """
    # Create basic project structure
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    pyproject = workspace / "pyproject.toml"
    pyproject.write_text("""[project]
name = "test-project"
version = "0.1.0"
""")

    changelog = workspace / "CHANGELOG.md"
    changelog.write_text("""# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]
""")

    return workspace
