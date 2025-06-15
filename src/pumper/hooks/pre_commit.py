"""Git pre-commit hook for version bumping."""

import os
import sys
from pathlib import Path
import subprocess
import typer
import tomli
import tomli_w
from typing import Optional

from ..core.commit import ConventionalCommit, BumpType
from ..core.version import Version, VersionBumpType
from ..logging import setup_logging, get_logger

# Set up centralized logging
setup_logging()
logger = get_logger()


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


def is_amend_commit(commit_message: str) -> bool:
    """Check if the current commit is an amend operation."""
    logger.info("=== Starting amend detection ===")

    try:
        # Method 0: Check environment variables that might indicate an amend
        git_editor = os.environ.get("GIT_EDITOR", "")
        git_sequence_editor = os.environ.get("GIT_SEQUENCE_EDITOR", "")
        git_reflog_action = os.environ.get("GIT_REFLOG_ACTION", "")

        logger.info(f"GIT_EDITOR: {git_editor}")
        logger.info(f"GIT_SEQUENCE_EDITOR: {git_sequence_editor}")
        logger.info(f"GIT_REFLOG_ACTION: {git_reflog_action}")

        if "amend" in git_reflog_action.lower():
            logger.info("GIT_REFLOG_ACTION indicates amend - skipping version bump")
            return True

        # Check if HEAD commit exists at all
        result = subprocess.run(
            ["git", "rev-parse", "--verify", "HEAD"],
            capture_output=True,
            text=True,
            check=False,
        )

        if result.returncode != 0:
            # No HEAD commit exists, so this can't be an amend
            logger.info("No HEAD commit exists - not an amend")
            return False

        # Method 1: Check for ORIG_HEAD existence AND verify it matches current HEAD
        # During amend, ORIG_HEAD points to the commit being amended (same as current HEAD)
        try:
            git_dir_result = subprocess.run(
                ["git", "rev-parse", "--git-dir"],
                capture_output=True,
                text=True,
                check=True,
            )
            git_dir = Path(git_dir_result.stdout.strip())

            orig_head_file = git_dir / "ORIG_HEAD"
            logger.info(f"ORIG_HEAD file exists: {orig_head_file.exists()}")

            if orig_head_file.exists():
                # Read ORIG_HEAD content
                orig_head_sha = orig_head_file.read_text().strip()

                # Get current HEAD SHA
                head_result = subprocess.run(
                    ["git", "rev-parse", "HEAD"],
                    capture_output=True,
                    text=True,
                    check=True,
                )
                current_head_sha = head_result.stdout.strip()

                logger.info(f"ORIG_HEAD: {orig_head_sha}")
                logger.info(f"Current HEAD: {current_head_sha}")

                # During amend, ORIG_HEAD equals current HEAD
                if orig_head_sha == current_head_sha:
                    logger.info("✓ ORIG_HEAD matches current HEAD - AMEND DETECTED")
                    return True
                else:
                    logger.info("✗ ORIG_HEAD != HEAD - not an amend")

        except (subprocess.CalledProcessError, FileNotFoundError, OSError) as e:
            logger.info(f"Could not check ORIG_HEAD: {e}")

        # Method 2: Compare with HEAD commit message as fallback
        result = subprocess.run(
            ["git", "log", "-1", "--pretty=format:%s%n%n%b"],
            capture_output=True,
            text=True,
            check=True,
        )
        head_message = result.stdout.strip()

        # Clean up the messages for comparison
        # Remove Git comment lines (lines starting with #) and extra whitespace
        def clean_commit_message(msg):
            lines = msg.split("\n")
            clean_lines = [line for line in lines if not line.strip().startswith("#")]
            return "\n".join(clean_lines).strip()

        clean_commit_message = clean_commit_message(commit_message)
        clean_head_message = head_message.strip()

        logger.info(f"Raw commit message: '{commit_message}'")
        logger.info(f"Clean commit message: '{clean_commit_message}'")
        logger.info(f"HEAD message: '{clean_head_message}'")
        logger.info(f"Messages equal: {clean_commit_message == clean_head_message}")

        # If the commit message being processed is identical to HEAD's message,
        # this is likely an amend operation
        if clean_commit_message == clean_head_message:
            logger.info("✓ Commit message matches HEAD - AMEND DETECTED")
            return True

        logger.info("✗ No amend indicators found - proceeding with version bump")
        return False

    except subprocess.CalledProcessError as e:
        logger.error(f"Git command failed during amend detection: {e}")
        # If we can't determine git state, assume it's not an amend
        return False


def update_version(
    message: str, cwd: Path, version_file_path: Optional[Path] = None
) -> Optional[str]:
    """Update version based on commit message."""
    try:
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
        except Exception as e:
            logger.debug(f"Git staging skipped: {e}")

        return str(new_version)

    except Exception as e:
        logger.error(f"Failed to update version: {e}")
        raise


def main(
    commit_msg_file: Path = typer.Argument(
        ...,
        help="Path to the commit message file",
        exists=True,
        file_okay=True,
        dir_okay=False,
        resolve_path=True,
    ),
) -> None:
    """Run the version bump pre-commit hook."""
    try:
        logger.info("🚀 Pumper hook starting...")

        # Read commit message
        message = commit_msg_file.read_text().strip()
        if not message:
            logger.info("Empty commit message - exiting")
            sys.exit(0)

        # Log basic info
        logger.info(f"Processing commit message: '{message}'")
        logger.info(f"Current working directory: {os.getcwd()}")
        logger.info(f"Commit message file: {commit_msg_file}")

        # Log all environment variables for debugging
        logger.info("=== Environment Variables ===")
        for key in sorted(os.environ.keys()):
            if "GIT" in key.upper() or key.upper() in ["PWD", "USER", "SHELL"]:
                logger.info(f"ENV {key}={os.environ[key]}")

        # Check if this is an amend commit
        if is_amend_commit(message):
            logger.info("🛑 AMEND DETECTED - Skipping version bump")
            typer.echo("Amend commit detected - skipping version bump")
            sys.exit(0)

        logger.info("✅ Not an amend - proceeding with version bump")

        # Update version
        new_version = update_version(message, get_repo_root())
        if new_version:
            logger.info(f"✨ Version bumped to {new_version}")
            typer.echo(f"✨ Version bumped to {new_version}")
        else:
            logger.info("No version bump needed")

        logger.info("✅ Pumper hook completed successfully")
        sys.exit(0)

    except Exception as e:
        logger.error(f"❌ Hook failed: {e}")
        import traceback

        logger.error(f"Traceback: {traceback.format_exc()}")
        sys.exit(1)


if __name__ == "__main__":
    typer.run(main)
