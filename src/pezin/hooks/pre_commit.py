"""Git commit-msg hook for version bumping (legacy/fallback mode).

This hook is maintained for backward compatibility and as a fallback
when the new prepare-commit-msg + post-commit hook system is not used.
"""

import contextlib
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional

import tomli
import tomli_w
import typer

from ..cli.commands import read_config
from ..core.commit import BumpType, ConventionalCommit
from ..core.version import Version, VersionBumpType, VersionFileConfig, VersionManager
from ..logging import get_logger, setup_logging

# Set up centralized logging
setup_logging()
logger = get_logger()

# Lock file to prevent conflicts with post-commit hook
LOCK_FILE = ".pezin_post_commit_lock"


def clean_commit_message(msg: str) -> str:
    """Clean up commit message by removing Git comment lines and extra whitespace.

    Args:
        msg: Raw commit message

    Returns:
        Cleaned commit message
    """
    lines = msg.split("\n")
    clean_lines = [line for line in lines if not line.strip().startswith("#")]
    return "\n".join(clean_lines).strip()


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


def is_post_commit_hook_active(repo_root: Path) -> bool:
    """Check if the post-commit hook is active to avoid conflicts."""
    lock_file = repo_root / LOCK_FILE
    return lock_file.exists()


def is_amend_commit(
    commit_source: Optional[str] = None,
    commit_sha: Optional[str] = None,
    commit_message: Optional[str] = None,
) -> bool:
    """Check if the current commit is an amend operation using prepare-commit-msg hook arguments.

    Args:
        commit_source: The source of the commit message (from prepare-commit-msg hook)
        commit_sha: The SHA of the commit being amended (from prepare-commit-msg hook)
        commit_message: The commit message content (for legacy compatibility)

    Returns:
        True if this is an amend operation, False otherwise
    """
    logger.info("Starting amend detection")
    logger.info(f"Commit source: {commit_source}")
    logger.info(f"Commit SHA: {commit_sha}")

    # Method 1: Use prepare-commit-msg hook arguments (most reliable)
    if commit_source == "commit":
        logger.info("Amend detected via prepare-commit-msg")
        if commit_sha:
            logger.debug(f"Amending commit: {commit_sha[:7]}")
        return True

    # Method 1.5: Check for rebase operations (should also be skipped)
    if commit_source in ["squash", "merge"]:
        logger.info(f"Git operation '{commit_source}' detected - skipping version bump")
        return True

    # Fallback methods for backward compatibility when hook arguments are not available
    try:
        # Method 2: Check for rebase operations in progress
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
                logger.info("Git rebase operation in progress - skipping version bump")
                return True

        # Method 3: Check environment variables that might indicate an amend or rebase
        git_reflog_action = os.environ.get("GIT_REFLOG_ACTION", "")

        if (
            "amend" in git_reflog_action.lower()
            or "rebase" in git_reflog_action.lower()
        ):
            logger.info(
                "GIT_REFLOG_ACTION indicates amend/rebase - skipping version bump"
            )
            return True

        # Check if HEAD commit exists at all
        head_result = subprocess.run(
            ["git", "rev-parse", "--verify", "HEAD"],
            capture_output=True,
            text=True,
            check=False,
        )

        if head_result.returncode != 0:
            # No HEAD commit exists, so this can't be an amend
            return False

        # Method 4: Check for ORIG_HEAD existence AND verify it matches current HEAD
        # During amend, ORIG_HEAD points to the commit being amended (same as current HEAD)
        # Only check this in a real Git repository context
        try:
            # Ensure we're in the correct Git repository context
            current_head_sha = head_result.stdout.strip()

            # Verify we can get the git directory relative to the current HEAD
            try:
                git_dir_result = subprocess.run(
                    ["git", "rev-parse", "--git-dir"],
                    capture_output=True,
                    text=True,
                    check=True,
                )
                git_dir = Path(git_dir_result.stdout.strip())
            except subprocess.CalledProcessError:
                # If we can't get git directory, skip ORIG_HEAD check
                return False

            orig_head_file = git_dir / "ORIG_HEAD"

            if orig_head_file.exists():
                # Read ORIG_HEAD content
                orig_head_sha = orig_head_file.read_text().strip()

                # During amend, ORIG_HEAD equals current HEAD
                # But also verify this is a recent operation by checking timestamps
                orig_head_mtime = orig_head_file.stat().st_mtime
                current_time = time.time()

                # Only consider ORIG_HEAD if it was modified recently (within last 60 seconds)
                if current_time - orig_head_mtime > 60:
                    return False

                if orig_head_sha == current_head_sha:
                    logger.info(
                        "ORIG_HEAD matches current HEAD and is recent - amend detected"
                    )
                    return True

        except (subprocess.CalledProcessError, OSError):
            pass

        # Method 5: Compare with HEAD commit message as fallback (for legacy compatibility)
        if commit_message:
            result = subprocess.run(
                ["git", "log", "-1", "--pretty=format:%s%n%n%b"],
                capture_output=True,
                text=True,
                check=True,
            )
            head_message = result.stdout.strip()

            # Clean up the messages for comparison
            clean_commit_message_text = clean_commit_message(commit_message)
            clean_head_message = head_message.strip()

            logger.info("Comparing commit messages for amend detection")
            logger.info(f"Clean commit message: '{clean_commit_message_text}'")
            logger.info(f"Clean HEAD message: '{clean_head_message}'")
            logger.info(
                f"Messages equal: {clean_commit_message_text == clean_head_message}"
            )

            # If the commit message being processed is identical to HEAD's message,
            # this is likely an amend operation
            if clean_commit_message_text == clean_head_message:
                logger.info("Commit message matches HEAD - amend detected")
                return True

        logger.info("No amend indicators found - proceeding with version bump")
        return False

    except subprocess.CalledProcessError as e:
        logger.error(f"Git command failed during amend detection: {e}")
        # If we can't determine git state, assume it's not an amend
        return False


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


def update_version(
    message: str,
    cwd: Path,
    version_file_path: Optional[Path] = None,
    config_file: Optional[Path] = None,
) -> Optional[str]:
    """Update version based on commit message using VersionManager."""
    try:
        # Skip version updates for fixup commits
        if ConventionalCommit.is_fixup_commit(message):
            logger.info("Fixup/squash commit - skipping version update")
            return None

        # Skip version updates for merge commits
        if ConventionalCommit.is_merge_commit(message):
            logger.info("Merge/git flow commit - skipping version update")
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
            if (config_file := find_config_file(cwd)) is None:
                # Fallback to legacy behavior
                config_file = cwd / "pyproject.toml"

        # Read configuration
        try:
            config = read_config(config_file)
        except Exception as e:
            logger.warning(f"Failed to read config from {config_file}: {e}")
            config = {}

        # Create VersionManager
        try:
            if config and "pezin" in config and config["pezin"]:
                # Only use pezin config if it has actual configuration
                version_manager = VersionManager.from_config(config["pezin"])
            elif version_file_path:
                version_manager = VersionManager(
                    [VersionFileConfig(path=version_file_path)]
                )
            else:
                # Default to the explicitly provided config file
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

            # Stage all updated files
            for file_path in updated_files:
                try:
                    subprocess.run(
                        ["git", "add", file_path], capture_output=True, check=False
                    )
                    logger.info(f"Staged file: {file_path}")
                except Exception as e:
                    logger.warning(f"Failed to stage {file_path}: {e}")

            return str(new_version)

        except Exception as e:
            logger.error(f"Failed to use VersionManager: {e}")
            # Fallback to legacy behavior
            return update_version_legacy(message, cwd, version_file_path)

    except Exception as e:
        logger.error(f"Failed to update version: {e}")
        raise


def update_version_legacy(
    message: str, cwd: Path, version_file_path: Optional[Path] = None
) -> Optional[str]:
    """Legacy version update function for backward compatibility."""
    try:
        # Skip version updates for fixup commits
        if ConventionalCommit.is_fixup_commit(message):
            logger.info("Fixup/squash commit - skipping legacy version update")
            return None

        # Skip version updates for merge commits
        if ConventionalCommit.is_merge_commit(message):
            logger.info("Merge/git flow commit - skipping legacy version update")
            return None

        commit = ConventionalCommit.parse(message)
        logger.info(f"Commit type: {commit.type}")

        bump_type = commit.get_bump_type()
        version_bump_type = convert_bump_type(bump_type)
        if version_bump_type is None:
            logger.info("No version bump needed")
            return None

        if version_file_path:
            version_file = version_file_path
        else:
            repo_root = get_repo_root()
            version_file = repo_root / "pyproject.toml"

        if not version_file.exists():
            raise ValueError(f"Version file not found: {version_file}")

        with open(version_file, "rb") as f:
            config = tomli.load(f)
            current = config["project"]["version"]
        logger.info(f"Current version: {current}")

        version = Version.parse(current)
        prerelease = commit.get_prerelease_label()
        new_version = version.bump(version_bump_type, prerelease)
        logger.info(f"Bumping to: {new_version}")

        config["project"]["version"] = str(new_version)
        with open(version_file, "wb") as f:
            tomli_w.dump(config, f)

        try:
            subprocess.run(
                ["git", "add", str(version_file)], capture_output=True, check=False
            )
            logger.info("Version file staged")
        except Exception:
            pass

        return str(new_version)

    except Exception as e:
        logger.error(f"Failed to update version: {e}")
        raise


def main(
    commit_msg_file: Optional[Path] = typer.Argument(
        None,
        help="Path to the commit message file (auto-detected if not provided)",
        exists=True,
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
    version_file: Optional[Path] = typer.Option(
        None,
        "--version-file",
        "-v",
        help="Path to version file (overrides config)",
        exists=True,
        file_okay=True,
        dir_okay=False,
        resolve_path=True,
    ),
    skip_amend_detection: bool = typer.Option(
        False,
        "--skip-amend-detection",
        help="Skip amend detection (useful for testing)",
        hidden=True,
    ),
) -> None:
    """Run the version bump hook with flexible configuration support.

    This hook can be used as either prepare-commit-msg or commit-msg hook.
    When used as prepare-commit-msg, Git provides additional arguments
    that enable reliable amend detection.

    Configuration can be provided via:
    1. --config option to specify config file path
    2. Auto-detection of pyproject.toml, pezin.toml, etc.
    3. --version-file option for simple single-file setups
    """
    try:
        repo_root = get_repo_root()

        # Check if post-commit hook is active to avoid conflicts
        if is_post_commit_hook_active(repo_root):
            show_status(
                "Post-commit hook is active - skipping commit-msg hook to avoid conflicts",
                "Post-commit hook handling version bumping",
            )
        # Auto-detect commit message file if not provided
        if commit_msg_file is None:
            try:
                git_dir = repo_root / ".git"

                # Handle worktree case
                if git_dir.is_file():
                    with open(git_dir) as f:
                        git_dir = Path(f.read().strip().split(": ")[1])

                commit_msg_file = git_dir / "COMMIT_EDITMSG"
                if not commit_msg_file.exists():
                    logger.error("Could not find commit message file")
                    sys.exit(1)

            except Exception as e:
                logger.error(f"Failed to auto-detect commit message file: {e}")
                sys.exit(1)

        # Read commit message
        message = commit_msg_file.read_text().strip()
        if not message:
            sys.exit(0)

        # Check if this is a fixup or squash commit
        if ConventionalCommit.is_fixup_commit(message):
            logger.info("Fixup/squash commit detected - skipping version bump")
            typer.echo("Fixup/squash commit detected - skipping version bump")
            sys.exit(0)

        # Check if this is a merge commit or git flow commit
        if ConventionalCommit.is_merge_commit(message):
            logger.info("Merge/git flow commit detected - skipping version bump")
            typer.echo("Merge/git flow commit detected - skipping version bump")
            sys.exit(0)

        # Check if this is an amend commit using simple and reliable method
        logger.info("Starting amend detection check")
        logger.info(f"skip_amend_detection: {skip_amend_detection}")
        logger.info(f"commit_source: {commit_source}, commit_sha: {commit_sha}")

        is_amend = False
        if not skip_amend_detection:
            # Simple amend detection: compare commit message with HEAD
            try:
                result = subprocess.run(
                    ["git", "log", "-1", "--pretty=format:%s"],
                    capture_output=True,
                    text=True,
                    check=True,
                )
                head_subject = result.stdout.strip()

                # Get the subject line from current commit message
                current_subject = message.split("\n")[0].strip()

                logger.info(f"HEAD subject: '{head_subject}'")
                logger.info(f"Current subject: '{current_subject}'")

                if head_subject == current_subject:
                    logger.info("Commit subjects match - this is likely an amend")
                    is_amend = True
                else:
                    logger.info("Commit subjects differ - this is a new commit")

            except subprocess.CalledProcessError as e:
                logger.info(f"Could not check HEAD commit: {e} - assuming new commit")

        if is_amend:
            logger.info("Amend detected - skipping version bump")
            show_status(
                "Amend detected - skipping version bump",
                "Amend commit detected - skipping version bump",
            )

        logger.info("Amend detection completed - proceeding with version bump")

        try:
            if new_version := update_version(
                message, repo_root, version_file, config_file
            ):
                logger.info(f"Version bumped to {new_version} (legacy mode)")
                typer.echo(f"Version bumped to {new_version} (files staged for commit)")
            else:
                typer.echo("No version bump needed")
        except ValueError as e:
            # Handle merge commits and non-conventional commits gracefully
            if "Merge commit" in str(e) or "Invalid commit header format" in str(e):
                logger.info(f"Skipping version bump: {e}")
                typer.echo("Skipping version bump for non-conventional commit")
                sys.exit(0)
            else:
                raise

        sys.exit(0)

    except Exception as e:
        logger.error(f"Hook failed: {e}")
        sys.exit(1)


def show_status(log_message, cli_message):
    logger.info(log_message)
    typer.echo(cli_message)
    sys.exit(0)


if __name__ == "__main__":
    typer.run(main)
