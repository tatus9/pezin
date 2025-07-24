"""Git post-commit hook for automatic version amendment and tagging."""

import contextlib
import os
import subprocess
import sys
from pathlib import Path
from typing import Optional

import typer

from ..cli.commands import read_config
from ..core.commit import BumpType, ConventionalCommit
from ..core.version import VersionBumpType, VersionFileConfig, VersionManager
from ..logging import get_logger, setup_logging

# Set up centralized logging
setup_logging()
logger = get_logger()

# Lock file to prevent infinite loops
LOCK_FILE = ".pezin_post_commit_lock"


def convert_bump_type(bump_type: BumpType) -> Optional[VersionBumpType]:
    """Convert BumpType to VersionBumpType."""
    if bump_type == BumpType.NONE:
        return None
    elif bump_type == BumpType.MAJOR:
        return VersionBumpType.MAJOR
    elif bump_type == BumpType.MINOR:
        return VersionBumpType.MINOR
    elif bump_type == BumpType.PATCH:
        return VersionBumpType.PATCH
    return None


def get_repo_root() -> Path:
    """Get the Git repository root directory."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            check=True,
        )
        return Path(result.stdout.strip())
    except subprocess.CalledProcessError as e:
        logger.error("Failed to determine repository root")
        raise ValueError("Not in a Git repository") from e


def is_lock_active(repo_root: Path) -> bool:
    """Check if the post-commit lock is active to prevent infinite loops."""
    lock_file = repo_root / LOCK_FILE
    return lock_file.exists()


def create_lock(repo_root: Path) -> None:
    """Create a lock file to prevent infinite loops."""
    lock_file = repo_root / LOCK_FILE
    lock_file.write_text(f"pezin post-commit lock created at {os.getpid()}")
    logger.debug(f"Created lock file: {lock_file}")


def remove_lock(repo_root: Path) -> None:
    """Remove the lock file."""
    lock_file = repo_root / LOCK_FILE
    if lock_file.exists():
        lock_file.unlink()
        logger.debug(f"Removed lock file: {lock_file}")


def should_skip_hook() -> bool:
    """Check if this commit should be skipped (merge, rebase, etc.)."""
    try:
        # Check for merge commits
        result = subprocess.run(
            ["git", "rev-parse", "--verify", "HEAD^2"],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode == 0:
            logger.info("Merge commit detected - skipping post-commit hook")
            return True

        # Check for rebase operations
        git_dir_result = subprocess.run(
            ["git", "rev-parse", "--git-dir"],
            capture_output=True,
            text=True,
            check=True,
        )
        git_dir = Path(git_dir_result.stdout.strip())

        rebase_merge_dir = git_dir / "rebase-merge"
        rebase_apply_dir = git_dir / "rebase-apply"

        if rebase_merge_dir.exists() or rebase_apply_dir.exists():
            logger.info("Rebase operation in progress - skipping post-commit hook")
            return True

        # Check environment variables
        git_reflog_action = os.environ.get("GIT_REFLOG_ACTION", "")
        if (
            "rebase" in git_reflog_action.lower()
            or "cherry-pick" in git_reflog_action.lower()
        ):
            logger.info(
                f"Git operation '{git_reflog_action}' - skipping post-commit hook"
            )
            return True

        return False

    except subprocess.CalledProcessError as e:
        logger.warning(f"Failed to check git state: {e}")
        return False


def get_last_commit_message() -> str:
    """Get the last commit message."""
    result = subprocess.run(
        ["git", "log", "-1", "--pretty=format:%s%n%n%b"],
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def find_config_file(cwd: Path) -> Optional[Path]:
    """Find the configuration file for pezin."""
    potential_configs = [
        cwd / "pyproject.toml",
        cwd / "pezin.toml",
        cwd / "setup.cfg",
        cwd / "package.json",
    ]

    for config_file in potential_configs:
        if config_file.exists():
            logger.info(f"Found config file: {config_file}")
            return config_file

    logger.info("No config file found")
    return None


def update_version_and_amend(
    message: str,
    repo_root: Path,
    config_file: Optional[Path] = None,
) -> Optional[str]:
    """Update version files and amend the commit with changes."""
    try:
        # Skip version updates for fixup commits
        if ConventionalCommit.is_fixup_commit(message):
            logger.info("Fixup/squash commit - skipping version update and amend")
            return None

        commit = ConventionalCommit.parse(message)
        logger.info(f"Commit type: {commit.type}")

        bump_type = commit.get_bump_type()
        version_bump_type = convert_bump_type(bump_type)
        if version_bump_type is None:
            logger.info("No version bump needed")
            return None

        # Find config file if not provided
        if config_file is None:
            if (config_file := find_config_file(repo_root)) is None:
                config_file = repo_root / "pyproject.toml"

        # Read configuration
        try:
            config = read_config(config_file)
        except Exception as e:
            logger.warning(f"Failed to read config from {config_file}: {e}")
            config = {}

        # Create VersionManager
        try:
            if config and "pezin" in config and config["pezin"]:
                version_manager = VersionManager.from_config(config["pezin"])
            else:
                version_manager = VersionManager([VersionFileConfig(path=config_file)])

            # Get current version
            current_version = version_manager.get_primary_version()
            if not current_version:
                raise ValueError("No version found in configured files")

            logger.info(f"Current version: {current_version}")

            # Calculate new version
            prerelease = commit.get_prerelease_label()
            new_version = current_version.bump(version_bump_type, prerelease)
            logger.info(f"Bumping to: {new_version}")

            # Update all configured files
            updated_files = version_manager.write_versions(new_version)
            logger.info(f"Updated files: {updated_files}")

            # Add all updated files to staging
            for file_path in updated_files:
                try:
                    subprocess.run(
                        ["git", "add", file_path],
                        capture_output=True,
                        check=True,
                        cwd=repo_root,
                    )
                    logger.info(f"Staged file for amendment: {file_path}")
                except subprocess.CalledProcessError as e:
                    logger.warning(f"Failed to stage {file_path}: {e}")

            # Amend the commit with the version changes
            subprocess.run(
                ["git", "commit", "--amend", "--no-edit"],
                capture_output=True,
                check=True,
                cwd=repo_root,
            )
            logger.info("Amended commit with version changes")

            return str(new_version)

        except Exception as e:
            logger.error(f"Failed to update version: {e}")
            return None

    except Exception as e:
        logger.error(f"Failed to parse commit or update version: {e}")
        return None


def create_git_tag(version: str, repo_root: Path) -> bool:
    """Create a git tag for the new version."""
    try:
        tag_name = f"v{version}"

        # Check if tag already exists
        result = subprocess.run(
            ["git", "tag", "-l", tag_name],
            capture_output=True,
            text=True,
            check=True,
            cwd=repo_root,
        )

        if result.stdout.strip():
            logger.info(f"Tag {tag_name} already exists")
            return False

        # Create annotated tag
        subprocess.run(
            ["git", "tag", "-a", tag_name, "-m", f"Release {version}"],
            capture_output=True,
            check=True,
            cwd=repo_root,
        )
        logger.info(f"Created tag: {tag_name}")
        return True

    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to create tag: {e}")
        return False


def main(
    config_file: Optional[Path] = typer.Option(
        None,
        "--config",
        "-c",
        help="Path to configuration file (auto-detected if not provided)",
        exists=True,
        file_okay=True,
        dir_okay=False,
        resolve_path=True,
    ),
    create_tag: bool = typer.Option(
        True,
        "--create-tag/--no-create-tag",
        help="Create git tag for new version",
    ),
) -> None:
    """Post-commit hook for automatic version amendment and tagging.

    This hook runs after a commit is created and:
    1. Checks if version bump is needed based on commit message
    2. Updates version files if needed
    3. Amends the commit to include version changes
    4. Creates git tag for the new version
    """
    try:
        core_flow(config_file, create_tag)
    except Exception as e:
        logger.error(f"Post-commit hook failed: {e}")
        # Always remove lock on error
        with contextlib.suppress(Exception):
            remove_lock(get_repo_root())
        sys.exit(1)


def core_flow(config_file, create_tag):
    logger.debug("Pezin post-commit hook starting...")

    repo_root = get_repo_root()

    # Check if we should skip this hook
    if should_skip_hook():
        logger.info("Skipping post-commit hook")
        sys.exit(0)

    # Check for skip flag from prepare-commit-msg hook (for amend detection)
    skip_flag = repo_root / ".pezin_skip_version_bump"
    if skip_flag.exists():
        reason = skip_flag.read_text().strip()
        logger.info(f"Skip flag found: {reason} - skipping version bump")
        try:
            skip_flag.unlink()
            logger.debug("Removed skip flag")
        except Exception as e:
            logger.warning(f"Failed to remove skip flag: {e}")
        sys.exit(0)

    # Check for lock to prevent infinite loops
    if is_lock_active(repo_root):
        logger.info("Post-commit lock active - skipping to prevent infinite loop")
        sys.exit(0)

    # Create lock
    create_lock(repo_root)

    try:
        # Get the commit message
        message = get_last_commit_message()
        if not message:
            logger.debug("Empty commit message - exiting")
            sys.exit(0)

        # Check if this is a fixup or squash commit
        if ConventionalCommit.is_fixup_commit(message):
            logger.info("Fixup/squash commit detected - skipping version bump")
            typer.echo("Fixup/squash commit detected - skipping version bump")
            sys.exit(0)

        logger.debug(f"Processing commit message: '{message}'")

        if new_version := update_version_and_amend(message, repo_root, config_file):
            logger.info(f"Version bumped to {new_version}")
            typer.echo(f"Version bumped to {new_version}")

            if create_tag:
                if create_git_tag(new_version, repo_root):
                    typer.echo(f"Created tag: v{new_version}")
                else:
                    typer.echo(f"Tag v{new_version} already exists or failed to create")
        else:
            logger.debug("No version bump needed")

    finally:
        # Always remove lock
        remove_lock(repo_root)

    logger.debug("Pezin post-commit hook completed successfully")
    sys.exit(0)


if __name__ == "__main__":
    typer.run(main)
