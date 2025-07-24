"""Git prepare-commit-msg hook for reliable amend detection."""

import contextlib
import os
import subprocess
import sys
from pathlib import Path
from typing import Optional

import typer

from ..core.commit import ConventionalCommit
from ..logging import get_logger, setup_logging

# Set up centralized logging
setup_logging()
logger = get_logger()


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


def is_amend_commit(
    commit_source: Optional[str] = None,
    commit_sha: Optional[str] = None,
) -> bool:
    """Check if the current commit is an amend operation using prepare-commit-msg hook arguments.

    Args:
        commit_source: The source of the commit message (from prepare-commit-msg hook)
        commit_sha: The SHA of the commit being amended (from prepare-commit-msg hook)

    Returns:
        True if this is an amend operation, False otherwise
    """
    logger.debug("Starting amend detection for prepare-commit-msg")
    logger.debug(f"Commit source: {commit_source}")
    logger.debug(f"Commit SHA: {commit_sha}")

    # Method 1: Use prepare-commit-msg hook arguments (most reliable)
    if commit_source == "commit":
        logger.info("Amend detected via prepare-commit-msg hook arguments")
        if commit_sha:
            logger.debug(f"Amending commit: {commit_sha[:7]}")
        return True

    # Method 2: Check for rebase operations (should also be skipped)
    if commit_source in ["squash", "merge"]:
        logger.info(f"Git operation '{commit_source}' detected - skipping validation")
        return True

    # Method 3: Check for rebase operations in progress
    with contextlib.suppress(subprocess.CalledProcessError):
        git_dir_result = subprocess.run(
            ["git", "rev-parse", "--git-dir"],
            capture_output=True,
            text=True,
            check=True,
        )
        git_dir = Path(git_dir_result.stdout.strip())

        # Check for rebase directories
        rebase_merge_dir = git_dir / "rebase-merge"
        rebase_apply_dir = git_dir / "rebase-apply"

        if rebase_merge_dir.exists() or rebase_apply_dir.exists():
            logger.info("Git rebase operation in progress - skipping validation")
            return True

    # Method 4: Check environment variables that might indicate an amend or rebase
    git_reflog_action = os.environ.get("GIT_REFLOG_ACTION", "")
    logger.debug(f"GIT_REFLOG_ACTION: {git_reflog_action}")

    if "amend" in git_reflog_action.lower() or "rebase" in git_reflog_action.lower():
        logger.info("GIT_REFLOG_ACTION indicates amend/rebase - skipping validation")
        return True

    logger.debug("No amend indicators found - this appears to be a new commit")
    return False


def should_skip_hook(commit_source: Optional[str] = None) -> bool:
    """Check if this commit should be skipped (merge, rebase, etc.)."""
    try:
        # Check for merge commits (only on new commits, not amends)
        if commit_source != "commit":
            result = subprocess.run(
                ["git", "rev-parse", "--verify", "HEAD^2"],
                capture_output=True,
                text=True,
                check=False,
            )
            if result.returncode == 0:
                logger.info("Merge commit detected - skipping prepare-commit-msg hook")
                return True

        return False

    except subprocess.CalledProcessError as e:
        logger.warning(f"Failed to check git state: {e}")
        return False


def validate_commit_message(message: str) -> bool:
    """Validate that the commit message follows conventional commit format.

    This is optional validation - we don't fail the commit, just warn.
    """
    try:
        # Skip validation for fixup commits
        if ConventionalCommit.is_fixup_commit(message):
            logger.debug(
                "Fixup/squash commit - skipping conventional format validation"
            )
            return True

        commit = ConventionalCommit.parse(message)
        logger.debug(f"Valid conventional commit: {commit.type}")
        return True
    except Exception as e:
        logger.debug(f"Not a conventional commit: {e}")
        return False


def main(
    commit_msg_file: Optional[Path] = typer.Argument(
        None,
        help="Path to the commit message file",
        exists=False,
        file_okay=True,
        dir_okay=False,
        resolve_path=True,
    ),
    commit_source: Optional[str] = typer.Argument(
        None, help="Source of the commit message (from prepare-commit-msg hook)"
    ),
    commit_sha: Optional[str] = typer.Argument(
        None, help="SHA of the commit being amended (from prepare-commit-msg hook)"
    ),
) -> None:
    """Prepare-commit-msg hook for reliable amend detection and validation.

    This hook runs before the commit message is finalized and:
    1. Detects amend operations reliably using hook arguments
    2. Validates commit message format (optional)
    3. Provides early feedback on commit conventions

    The actual version bumping is handled by the post-commit hook.
    """
    try:
        commit_analysis(commit_msg_file, commit_source, commit_sha)
    except Exception as e:
        logger.error(f"Prepare-commit-msg hook failed: {e}")
        import traceback

        logger.debug(f"Traceback: {traceback.format_exc()}")
        # Don't fail the commit on hook errors
        sys.exit(0)


def commit_analysis(commit_msg_file, commit_source, commit_sha):
    logger.debug("Pezin prepare-commit-msg hook starting...")

    # Log hook arguments for debugging
    logger.debug(
        f"Hook arguments: file={commit_msg_file}, source={commit_source}, sha={commit_sha}"
    )

    # Handle case where commit_msg_file is not provided (e.g., during rebase)
    if commit_msg_file is None:
        logger.debug("No commit message file provided - likely during rebase")
        # During rebase, we should skip version bumping to avoid conflicts
        if commit_source in ["squash", "merge"] or is_amend_commit(
            commit_source, commit_sha
        ):
            logger.info("Rebase/squash/merge operation detected - creating skip flag")
            try:
                repo_root = get_repo_root()
                skip_flag = repo_root / ".pezin_skip_version_bump"
                skip_flag.write_text("rebase_operation")
                logger.debug(f"Created skip flag: {skip_flag}")
            except Exception as e:
                logger.warning(f"Failed to create skip flag: {e}")
        sys.exit(0)

    # Ensure the file exists before proceeding
    if not commit_msg_file.exists():
        logger.debug(f"Commit message file {commit_msg_file} does not exist - exiting")
        sys.exit(0)

    # Check if we should skip this hook
    if should_skip_hook(commit_source):
        logger.info("Skipping prepare-commit-msg hook")
        sys.exit(0)

    # Check if this is an amend commit
    if is_amend_commit(commit_source, commit_sha):
        logger.info("Amend detected - creating skip flag for post-commit hook")
        # Create a flag file to tell post-commit hook to skip version bump
        try:
            repo_root = get_repo_root()
            skip_flag = repo_root / ".pezin_skip_version_bump"
            skip_flag.write_text("amend")
            logger.debug(f"Created skip flag: {skip_flag}")
        except Exception as e:
            logger.warning(f"Failed to create skip flag: {e}")
        sys.exit(0)

    # Read commit message
    message = commit_msg_file.read_text().strip()
    if not message:
        logger.debug("Empty commit message - exiting")
        sys.exit(0)

    # Check if this is a fixup or squash commit
    if ConventionalCommit.is_fixup_commit(message):
        logger.info(
            "Fixup/squash commit detected - creating skip flag for post-commit hook"
        )
        try:
            repo_root = get_repo_root()
            skip_flag = repo_root / ".pezin_skip_version_bump"
            skip_flag.write_text("fixup_commit")
            logger.debug(f"Created skip flag: {skip_flag}")
        except Exception as e:
            logger.warning(f"Failed to create skip flag: {e}")
        sys.exit(0)

    # Log basic info
    logger.debug(f"Processing commit message: '{message}'")
    logger.debug(f"Current working directory: {os.getcwd()}")

    # Log relevant environment variables for debugging
    logger.debug("=== Environment Variables ===")
    for key in sorted(os.environ.keys()):
        if "GIT" in key.upper() and key in ["GIT_REFLOG_ACTION", "GIT_EDITOR"]:
            logger.debug(f"ENV {key}={os.environ[key]}")

    # Validate commit message format (optional - don't fail on invalid)
    if validate_commit_message(message):
        logger.debug("Commit message follows conventional format")
    else:
        logger.debug(
            "Commit message does not follow conventional format - version bump may not occur"
        )

    logger.debug("Prepare-commit-msg hook completed successfully")
    sys.exit(0)


if __name__ == "__main__":
    typer.run(main)
