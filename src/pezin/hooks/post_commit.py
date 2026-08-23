"""Git post-commit hook for automatic version amendment and tagging."""

import contextlib
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

import typer

from ..cli.commands import get_git_repo_url, read_config
from ..core.changelog import ChangelogConfig, ChangelogManager
from ..core.commit import BumpType, ConventionalCommit
from ..core.config import (
    ChangelogHookConfig,
    ServiceConfig,
    is_monorepo_mode,
    read_changelog_config,
)
from ..core.version import (
    ServiceVersionManager,
    VersionBumpType,
    VersionFileConfig,
    VersionManager,
)
from ..logging import get_logger, setup_logging
from .safety import atomic_worktree_guard, find_parked_patch_conflicts, take_hook_start

# Set up centralized logging
setup_logging()
logger = get_logger()

# Lock file to prevent infinite loops
LOCK_FILE = ".pezin_post_commit_lock"


def echo_to_terminal(message: str) -> None:
    """Write message directly to terminal, bypassing pre-commit's capture.

    Pre-commit framework captures stdout/stderr from hooks. To ensure user
    feedback is visible, we write directly to /dev/tty when available.
    Falls back to stderr if tty is not available.
    """
    try:
        with open("/dev/tty", "w") as tty:
            tty.write(f"{message}\n")
            tty.flush()
    except (OSError, IOError):
        # Fallback to stderr if /dev/tty is not available (e.g., in CI)
        typer.echo(message, err=True)


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


@dataclass
class VersionUpdateResult:
    """Result of a version update operation.

    Attributes:
        versions: List of new version strings
        tags: List of tag names to create
        is_monorepo: Whether this was a monorepo update
    """

    versions: List[str]
    tags: List[str]
    is_monorepo: bool = False


def _service_root(service: ServiceConfig, repo_root: Path) -> Path:
    """Best-effort service root: directory of the first version file, else repo root."""
    if service.version_files:
        first = Path(service.version_files[0].path)
        return (
            first.parent
            if first.is_absolute()
            else (repo_root / first).resolve().parent
        )
    return repo_root


def _collect_write_targets(pezin_config: dict, repo_root: Path) -> set:
    """Compute the repo-relative paths pezin may rewrite during this commit.

    Used for two safety checks: detecting parked pre-commit patches that
    overlap these files (skip the bump) and snapshotting them for the atomic
    rollback guard.  Mirrors the write surface of ``update_single_version``
    and ``update_monorepo_versions``: version files plus, when enabled, the
    changelog path(s).
    """
    targets: set = set()

    if is_monorepo_mode(pezin_config):
        service_manager = ServiceVersionManager.from_config(pezin_config)
        for service in service_manager.config.services:
            for version_file in service.version_files:
                targets.add(str(Path(version_file.path)))
            changelog_config = service_manager.get_changelog_config(service.name)
            if changelog_config.enabled:
                changelog_path = Path(changelog_config.path)
                if not changelog_path.is_absolute():
                    base_dir = _service_root(service, repo_root)
                    changelog_path = (base_dir / changelog_path).resolve()
                targets.add(str(changelog_path))
    else:
        version_manager = VersionManager.from_config(pezin_config)
        for config_file in version_manager.config_files:
            targets.add(str(Path(config_file.path)))
        changelog_config = read_changelog_config(pezin_config)
        if changelog_config.enabled:
            changelog_path = Path(changelog_config.path)
            if not changelog_path.is_absolute():
                changelog_path = (repo_root / changelog_path).resolve()
            targets.add(str(changelog_path))

    return targets


def write_changelog_entry(
    commit: ConventionalCommit,
    new_version: str,
    base_dir: Path,
    changelog_config: ChangelogHookConfig,
) -> Optional[Path]:
    """Write the new version's CHANGELOG section, return the path on success.

    Returns None when the write is skipped (`enabled = False`) or on failure.
    Failures are logged via `echo_to_terminal` and never re-raised so the
    caller can continue with the version amend regardless.
    """
    if not changelog_config.enabled:
        return None

    try:
        changelog_path = Path(changelog_config.path)
        if not changelog_path.is_absolute():
            changelog_path = (base_dir / changelog_path).resolve()

        manager = ChangelogManager(
            ChangelogConfig(
                unreleased_label=changelog_config.unreleased_label,
                repo_url=get_git_repo_url(),
            )
        )
        manager.create_if_missing(changelog_path)
        manager.update_changelog(changelog_path, new_version, [commit])
        logger.info(f"Updated changelog: {changelog_path}")
        return changelog_path

    except Exception as e:
        # Non-fatal: log + warn user; the version bump must still land.
        logger.warning(f"CHANGELOG write failed: {e}", exc_info=True)
        echo_to_terminal(f"[pezin] Warning: CHANGELOG write failed: {e}")
        return None


def update_monorepo_versions(
    commit: ConventionalCommit,
    version_bump_type: VersionBumpType,
    pezin_config: dict,
    repo_root: Path,
    write_targets: Optional[set] = None,
) -> Optional[VersionUpdateResult]:
    """Update versions for monorepo services based on commit scope.

    Args:
        commit: Parsed conventional commit
        version_bump_type: Type of version bump to perform
        pezin_config: Pezin configuration dictionary
        repo_root: Repository root path
        write_targets: Repo-relative paths pezin may rewrite; snapshotted for
            the atomic rollback guard (computed when omitted)

    Returns:
        VersionUpdateResult with updated versions and tags, or None if no update
    """
    try:
        service_manager = ServiceVersionManager.from_config(pezin_config)
        scopes = commit.get_scopes()

        # Get services to bump
        if scopes:
            services, unknown = service_manager.get_services_for_scopes(scopes)
            if unknown:
                logger.warning(f"Unknown scopes (no matching services): {unknown}")
        else:
            # No scope provided
            if service_manager.config.require_scope:
                logger.error("Monorepo mode requires a scope in commit message")
                return None

            if default_service := service_manager.get_default_service():
                services = [default_service]
                logger.info(f"Using default service: {default_service.name}")
            else:
                logger.info("No scope and no default service - skipping version bump")
                return None

        if not services:
            logger.info("No services matched for scope(s) - skipping version bump")
            return None

        # Bump versions for matched services, restoring everything on failure
        prerelease = commit.get_prerelease_label()
        if write_targets is None:
            write_targets = _collect_write_targets(pezin_config, repo_root)
        with atomic_worktree_guard(repo_root, write_targets):
            results = service_manager.bump_services(
                services, version_bump_type, prerelease
            )

            if not results:
                logger.warning("No versions were bumped")
                return None

            # Collect all updated files and stage them
            all_updated_files = []
            for result in results:
                all_updated_files.extend(result.updated_files)
                logger.info(
                    f"Service {result.service_name}: "
                    f"{result.old_version} -> {result.new_version}"
                )

            # Write per-service changelog entries before staging.
            for result in results:
                service = next(
                    (s for s in services if s.name == result.service_name), None
                )
                if service is None:
                    continue
                cl_config = service_manager.get_changelog_config(service.name)
                base_dir = _service_root(service, repo_root)
                written = write_changelog_entry(
                    commit, str(result.new_version), base_dir, cl_config
                )
                if written is not None:
                    all_updated_files.append(str(written))

            # Stage all updated files
            for file_path in all_updated_files:
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

            # Amend the commit (skip hooks since original commit already passed them)
            subprocess.run(
                ["git", "commit", "--amend", "--no-edit", "--no-verify"],
                capture_output=True,
                check=True,
                cwd=repo_root,
            )
            logger.info("Amended commit with version changes")

            return VersionUpdateResult(
                versions=[str(r.new_version) for r in results],
                tags=[r.tag_name for r in results],
                is_monorepo=True,
            )

    except Exception as e:
        logger.error(f"Failed to update monorepo versions: {e}")
        return None


def update_single_version(
    commit: ConventionalCommit,
    version_bump_type: VersionBumpType,
    pezin_config: dict,
    config_file: Path,
    repo_root: Path,
    write_targets: Optional[set] = None,
) -> Optional[VersionUpdateResult]:
    """Update version for single-repo mode (original behavior).

    Args:
        commit: Parsed conventional commit
        version_bump_type: Type of version bump to perform
        pezin_config: Pezin configuration dictionary
        config_file: Path to configuration file
        repo_root: Repository root path
        write_targets: Repo-relative paths pezin may rewrite; snapshotted for
            the atomic rollback guard (computed when omitted)

    Returns:
        VersionUpdateResult with updated version and tag, or None if no update
    """
    try:
        if pezin_config:
            version_manager = VersionManager.from_config(pezin_config)
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

        if write_targets is None:
            write_targets = _collect_write_targets(pezin_config, repo_root)
        with atomic_worktree_guard(repo_root, write_targets):
            # Update all configured files
            updated_files = version_manager.write_versions(new_version)
            logger.info(f"Updated files: {updated_files}")

            # Write the changelog entry before staging so it lands in the same amend.
            cl_config = read_changelog_config(pezin_config)
            written = write_changelog_entry(
                commit, str(new_version), repo_root, cl_config
            )
            if written is not None:
                updated_files.append(str(written))

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

            # Amend the commit with the version changes (skip hooks since original passed)
            subprocess.run(
                ["git", "commit", "--amend", "--no-edit", "--no-verify"],
                capture_output=True,
                check=True,
                cwd=repo_root,
            )
            logger.info("Amended commit with version changes")

            return VersionUpdateResult(
                versions=[str(new_version)],
                tags=[f"v{new_version}"],
                is_monorepo=False,
            )

    except Exception as e:
        logger.error(f"Failed to update version: {e}")
        return None


def update_version_and_amend(
    message: str,
    repo_root: Path,
    config_file: Optional[Path] = None,
) -> Optional[VersionUpdateResult]:
    """Update version files and amend the commit with changes.

    Supports both single-repo and monorepo modes. In monorepo mode,
    commit scopes are used to determine which services to bump.

    Args:
        message: Commit message
        repo_root: Repository root path
        config_file: Optional path to configuration file

    Returns:
        VersionUpdateResult with updated versions and tags, or None if no update
    """
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

        pezin_config = config.get("pezin", {}) if config else {}

        # Never rewrite files whose unstaged changes pre-commit has parked:
        # a bump here makes the parked-patch restore fail and the user's
        # unstaged work is dropped from the worktree.
        write_targets = _collect_write_targets(pezin_config, repo_root)
        conflicts = find_parked_patch_conflicts(
            repo_root, write_targets, since=take_hook_start(repo_root)
        )
        if conflicts:
            overlapping = ", ".join(sorted(conflicts))
            logger.warning(
                "Skipping version bump: pre-commit parked unstaged changes "
                f"overlap files pezin would rewrite: {overlapping}"
            )
            echo_to_terminal(
                "[pezin] Skipping version bump: unstaged changes to version "
                f"files are parked by pre-commit: {overlapping}"
            )
            echo_to_terminal(
                "[pezin] Rewriting them can corrupt the parked-patch restore "
                "and lose those changes."
            )
            echo_to_terminal(
                "[pezin] Stash or commit those changes first, then commit "
                "again or run `pezin bump`."
            )
            return None

        # Check if monorepo mode
        if is_monorepo_mode(pezin_config):
            logger.info("Monorepo mode detected")
            return update_monorepo_versions(
                commit, version_bump_type, pezin_config, repo_root, write_targets
            )
        else:
            return update_single_version(
                commit,
                version_bump_type,
                pezin_config,
                config_file,
                repo_root,
                write_targets,
            )

    except Exception as e:
        logger.error(f"Failed to parse commit or update version: {e}")
        return None


def create_git_tag(
    version: str, repo_root: Path, tag_name: Optional[str] = None
) -> bool:
    """Create a git tag for the new version.

    Args:
        version: Version string for the tag message
        repo_root: Repository root path
        tag_name: Custom tag name (default: "v{version}")

    Returns:
        True if tag was created, False if already exists or failed
    """
    try:
        if tag_name is None:
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
        echo_to_terminal(f"[pezin] Error: {e}")
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
        echo_to_terminal("[pezin] Skipping: merge/rebase operation detected")
        sys.exit(0)

    # Check for skip flag from prepare-commit-msg hook (for amend detection)
    skip_flag = repo_root / ".pezin_skip_version_bump"
    if skip_flag.exists():
        reason = skip_flag.read_text().strip()
        logger.info(f"Skip flag found: {reason} - skipping version bump")
        echo_to_terminal(f"[pezin] Skipping: {reason} detected")
        try:
            skip_flag.unlink()
            logger.debug("Removed skip flag")
        except Exception as e:
            logger.warning(f"Failed to remove skip flag: {e}")
        sys.exit(0)

    # Check for lock to prevent infinite loops
    if is_lock_active(repo_root):
        logger.info("Post-commit lock active - skipping to prevent infinite loop")
        echo_to_terminal("[pezin] Skipping: already processing (lock active)")
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

        if result := update_version_and_amend(message, repo_root, config_file):
            # Handle version bump result
            for version in result.versions:
                logger.info(f"Version bumped to {version}")
                echo_to_terminal(f"[pezin] Version bumped to {version}")

            if create_tag:
                # Create tags (use custom tag names for monorepo mode)
                for i, tag_name in enumerate(result.tags):
                    version = (
                        result.versions[i] if i < len(result.versions) else tag_name
                    )
                    if create_git_tag(version, repo_root, tag_name):
                        echo_to_terminal(f"[pezin] Created tag: {tag_name}")
                    else:
                        echo_to_terminal(
                            f"[pezin] Tag {tag_name} already exists or failed to create"
                        )
        else:
            # Parse commit to provide helpful feedback about why no bump occurred
            try:
                commit = ConventionalCommit.parse(message)
                echo_to_terminal(
                    f"[pezin] No version bump: '{commit.type.value}' "
                    "commits don't trigger version bumps"
                )
            except Exception:
                echo_to_terminal(
                    "[pezin] No version bump: commit doesn't match conventions"
                )
            logger.debug("No version bump needed")

    finally:
        # Always remove lock
        remove_lock(repo_root)

    logger.debug("Pezin post-commit hook completed successfully")
    sys.exit(0)


if __name__ == "__main__":
    typer.run(main)
