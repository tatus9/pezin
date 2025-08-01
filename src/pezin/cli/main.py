"""CLI entry point for pezin tool."""

import contextlib
import logging
import subprocess

# Set up logging conditionally based on command
import sys
from pathlib import Path
from typing import List, Optional, Tuple

import tomli
import typer
from rich.console import Console

from ..core.version import VersionBumpType
from ..logging import get_logger, setup_logging
from . import commands, hooks

# Check if this is a version-only command
is_version_command = any(arg in ["--version", "-v", "version"] for arg in sys.argv[1:])

if not is_version_command:
    setup_logging()
else:
    # For version commands, suppress all logging output
    logging.getLogger().setLevel(logging.CRITICAL)
    # Also suppress all pezin module loggers
    for logger_name in [
        "pezin",
        "pezin.cli",
        "pezin.cli.commands",
        "pezin.core",
        "pezin.hooks",
    ]:
        logging.getLogger(logger_name).setLevel(logging.CRITICAL)

# Always get logger, but conditionally set up logging
logger = get_logger()

# Initialize Typer app and console
app = typer.Typer(
    help="Version management and changelog tool for semantic versioning",
    add_completion=False,
    no_args_is_help=True,
)

console = Console()


def get_pezin_version() -> str:
    """Get the pezin version."""
    # Try to get version from package metadata first
    try:
        import importlib.metadata

        return importlib.metadata.version("pezin")
    except importlib.metadata.PackageNotFoundError:
        # Fallback to reading from pyproject.toml in development
        try:
            return get_version_from_pyproject_dev()
        except Exception:
            return "unknown"


def get_version_from_pyproject_dev():
    project_root = Path(__file__).parents[3]  # src/pezin/cli/main.py -> project root
    pyproject_path = project_root / "pyproject.toml"
    if not pyproject_path.exists():
        return "unknown"
    with open(pyproject_path, "rb") as f:
        data = tomli.load(f)
    version = data.get("project", {}).get("version", "unknown")
    return f"{version} (development)"


def get_version_quietly(config_file: Path) -> Optional[str]:
    """Get version from config file without verbose logging."""
    try:
        if config_file.suffix == ".toml":
            with open(config_file, "rb") as f:
                data = tomli.load(f)

            # Try project section first
            if "project" in data and "version" in data["project"]:
                return data["project"]["version"]

            # Try pezin section next
            if "pezin" in data and "version" in data["pezin"]:
                return data["pezin"]["version"]

            # Try tool.pezin section
            if (
                "tool" in data
                and "pezin" in data["tool"]
                and "version" in data["tool"]["pezin"]
            ):
                return data["tool"]["pezin"]["version"]

        elif config_file.suffix == ".json":
            import json

            with open(config_file, "r") as f:
                data = json.load(f)
                if "version" in data:
                    return data["version"]

        return None
    except Exception:
        return None


def get_current_project_info() -> Tuple[Optional[str], Optional[str]]:
    """Get current directory project name and version if 100% confident.

    Returns:
        Tuple of (project_name, version) or (None, None) if not confident
    """
    try:
        # Import find_config_file locally to avoid triggering logging setup

        def find_config_file_local(cwd: Path) -> Optional[Path]:
            """Local version of find_config_file to avoid logging setup."""
            potential_configs = [
                cwd / "pyproject.toml",
                cwd / "pezin.toml",
                cwd / "setup.cfg",
                cwd / "package.json",
            ]
            for config_file in potential_configs:
                if config_file.exists():
                    return config_file
            return None

        # Find config file in current directory
        cwd = Path.cwd()
        config_file = find_config_file_local(cwd)
        if not config_file:
            return None, None

        # Get project version using existing robust functionality
        # For version commands, avoid verbose logging by using minimal version reading
        if is_version_command:
            project_version = get_version_quietly(config_file)
        else:
            project_version = commands.get_current_version(config_file)
        if not project_version:
            return None, None

        # Try to get project name from the config file
        project_name = None
        with contextlib.suppress(Exception):
            if config_file.suffix == ".toml":
                with open(config_file, "rb") as f:
                    data = tomli.load(f)

                # Try different locations for project name
                if "project" in data and "name" in data["project"]:
                    project_name = data["project"]["name"]
                elif "name" in data:
                    project_name = data["name"]
                elif (
                    "tool" in data
                    and "pezin" in data["tool"]
                    and "name" in data["tool"]["pezin"]
                ):
                    project_name = data["tool"]["pezin"]["name"]

            elif config_file.suffix == ".json":  # package.json
                with open(config_file, "r") as f:
                    import json

                    data = json.load(f)
                    if "name" in data:
                        project_name = data["name"]

        # Only return if we have at least a version, name is optional
        return (project_name, project_version) if project_version else (None, None)
    except Exception:
        # Any error means we're not 100% confident
        return None, None


def validate_prerelease(value: Optional[str]) -> Optional[str]:
    """Validate pre-release label."""
    if value is not None and value not in ["alpha", "beta", "rc"]:
        raise typer.BadParameter("Must be one of: alpha, beta, rc")
    return value


def version_callback(value: bool) -> None:
    """Global version callback."""
    if value:
        # Try to get current project info first
        project_name, project_version = get_current_project_info()
        pezin_version = get_pezin_version()

        # Show project version if we found one and it's not pezin itself
        if project_version and project_name != "pezin":
            if project_name:
                console.print(f"{project_name} {project_version}")
            else:
                console.print(project_version)

        # Always show pezin version
        console.print(f"pezin {pezin_version}")
        raise typer.Exit()


@app.command(name="version")
def version_command() -> None:
    """Show pezin version and exit."""
    # Try to get current project info first
    project_name, project_version = get_current_project_info()
    pezin_version = get_pezin_version()

    # Show project version if we found one and it's not pezin itself
    if project_version and project_name != "pezin":
        if project_name:
            console.print(f"{project_name} {project_version}")
        else:
            console.print(project_version)

    # Always show pezin version
    console.print(f"pezin {pezin_version}")


@app.callback()
def main(
    version: Optional[bool] = typer.Option(
        None,
        "--version",
        "-v",
        callback=version_callback,
        is_eager=True,
        help="Show version and exit",
    ),
) -> None:
    """Version management and changelog tool for semantic versioning."""
    pass


def _is_amend_commit_with_args(
    commit_source: Optional[str], commit_sha: Optional[str], commit_message: str
) -> bool:
    """Check if the current commit is an amend operation using prepare-commit-msg hook arguments.

    Args:
        commit_source: The source of the commit message (from prepare-commit-msg hook)
        commit_sha: The SHA of the commit being amended (from prepare-commit-msg hook)
        commit_message: The commit message content

    Returns:
        True if this is an amend operation, False otherwise
    """
    # Import here to avoid circular imports
    from ..hooks.pre_commit import is_amend_commit

    # Use the unified amend detection function
    return is_amend_commit(commit_source, commit_sha, commit_message)


def _is_amend_commit(commit_message: str) -> bool:
    """Check if the current commit is an amend operation using legacy methods."""
    try:
        # Check if HEAD commit exists at all
        result = subprocess.run(
            ["git", "rev-parse", "--verify", "HEAD"],
            capture_output=True,
            text=True,
            check=False,
        )

        if result.returncode != 0:
            # No HEAD commit exists, so this can't be an amend
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

                # During amend, ORIG_HEAD equals current HEAD
                if orig_head_sha == current_head_sha:
                    return True
        except (subprocess.CalledProcessError, OSError):
            pass

        # Method 2: Compare with HEAD commit message as fallback
        result = subprocess.run(
            ["git", "log", "-1", "--pretty=format:%s%n%n%b"],
            capture_output=True,
            text=True,
            check=True,
        )
        head_message = result.stdout.strip()

        # Clean up the messages for comparison (remove extra whitespace)
        clean_commit_message = commit_message.strip()
        clean_head_message = head_message.strip()

        # If the commit message being processed is identical to HEAD's message,
        # this is likely an amend operation
        return clean_commit_message == clean_head_message

    except subprocess.CalledProcessError:
        # If we can't determine git state, assume it's not an amend
        return False


def handle_version_bump(
    bump_type: VersionBumpType,
    config_file: Path,
    dry_run: bool,
    prerelease: Optional[str],
    skip_changelog: bool,
    changelog_file: Path,
    message: Optional[List[str]],
) -> None:
    """Handle the version bump operation with proper error handling."""
    try:
        # Read config first
        config = commands.read_config(config_file)

        # Read current version
        try:
            current, version_file = commands.get_version_info(config_file, config)
            logger.debug(f"Current version {current} from {version_file}")
        except (FileNotFoundError, ValueError) as e:
            console.print(f"[red]Error:[/] {str(e)}")
            raise typer.Exit(1) from e
        # Get commits
        commits = []
        if message:
            for msg in message:
                try:
                    commits.append(commands.ConventionalCommit.parse(msg))
                except ValueError as exc:
                    console.print(f"[red]Error:[/] Invalid commit message: {msg}")
                    raise typer.Exit(1) from exc
        else:
            commits = commands.get_commits_since_last_tag()
            if not commits:
                console.print("[yellow]Warning:[/] No conventional commits found")

        # Perform version bump
        if new_version := commands.bump_version(
            bump_type,
            version_file,
            config=config,
            dry_run=dry_run,
            prerelease=prerelease,
        ):
            if dry_run:
                console.print(
                    f"[blue]Dry run:[/] Would bump {current} -> {new_version}"
                )
            else:
                console.print(f"[green]Version bumped: {current} -> {new_version}[/]")

            # Update changelog
            if not skip_changelog:
                if commands.update_changelog(
                    new_version, commits, changelog_file, dry_run, config=config
                ):
                    if not dry_run:
                        actual_file = commands.get_changelog_file(
                            config, changelog_file
                        )
                        console.print(f"[green]Updated {actual_file}[/]")
                else:
                    console.print("[red]Error:[/] Failed to update changelog")

            return

        console.print("[yellow]No version change needed[/]")

    except Exception as e:
        console.print(f"[red]Error:[/] {str(e)}")
        raise typer.Exit(1) from e


@app.command(name="patch")
def patch_command(
    config_file: Path = typer.Option(
        "pyproject.toml",
        "--config",
        help="Path to project config file",
        exists=False,
        file_okay=True,
        dir_okay=False,
        resolve_path=True,
    ),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Show what would be done without making changes"
    ),
    prerelease: Optional[str] = typer.Option(
        None,
        "--pre",
        callback=validate_prerelease,
        help="Pre-release label (alpha, beta, rc)",
    ),
    skip_changelog: bool = typer.Option(
        False, "--skip-changelog", help="Skip updating the changelog"
    ),
    changelog_file: Path = typer.Option(
        "CHANGELOG.md",
        "--changelog",
        help="Path to changelog file",
        exists=False,
        file_okay=True,
        dir_okay=False,
        resolve_path=True,
    ),
    message: Optional[List[str]] = typer.Option(
        None,
        "--message",
        "-m",
        help="Commit message(s) to use (can be specified multiple times)",
    ),
) -> None:
    """Create a patch version bump (bug fixes)."""
    handle_version_bump(
        VersionBumpType.PATCH,
        config_file,
        dry_run,
        prerelease,
        skip_changelog,
        changelog_file,
        message,
    )


@app.command(name="minor")
def minor_command(
    config_file: Path = typer.Option(
        "pyproject.toml",
        "--config",
        help="Path to project config file",
        exists=False,
        file_okay=True,
        dir_okay=False,
        resolve_path=True,
    ),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Show what would be done without making changes"
    ),
    prerelease: Optional[str] = typer.Option(
        None,
        "--pre",
        callback=validate_prerelease,
        help="Pre-release label (alpha, beta, rc)",
    ),
    skip_changelog: bool = typer.Option(
        False, "--skip-changelog", help="Skip updating the changelog"
    ),
    changelog_file: Path = typer.Option(
        "CHANGELOG.md",
        "--changelog",
        help="Path to changelog file",
        exists=False,
        file_okay=True,
        dir_okay=False,
        resolve_path=True,
    ),
    message: Optional[List[str]] = typer.Option(
        None,
        "--message",
        "-m",
        help="Commit message(s) to use (can be specified multiple times)",
    ),
) -> None:
    """Create a minor version bump (new features)."""
    handle_version_bump(
        VersionBumpType.MINOR,
        config_file,
        dry_run,
        prerelease,
        skip_changelog,
        changelog_file,
        message,
    )


@app.command(name="major")
def major_command(
    config_file: Path = typer.Option(
        "pyproject.toml",
        "--config",
        help="Path to project config file",
        exists=False,
        file_okay=True,
        dir_okay=False,
        resolve_path=True,
    ),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Show what would be done without making changes"
    ),
    prerelease: Optional[str] = typer.Option(
        None,
        "--pre",
        callback=validate_prerelease,
        help="Pre-release label (alpha, beta, rc)",
    ),
    skip_changelog: bool = typer.Option(
        False, "--skip-changelog", help="Skip updating the changelog"
    ),
    changelog_file: Path = typer.Option(
        "CHANGELOG.md",
        "--changelog",
        help="Path to changelog file",
        exists=False,
        file_okay=True,
        dir_okay=False,
        resolve_path=True,
    ),
    message: Optional[List[str]] = typer.Option(
        None,
        "--message",
        "-m",
        help="Commit message(s) to use (can be specified multiple times)",
    ),
) -> None:
    """Create a major version bump (breaking changes)."""
    handle_version_bump(
        VersionBumpType.MAJOR,
        config_file,
        dry_run,
        prerelease,
        skip_changelog,
        changelog_file,
        message,
    )


@app.command(name="hook")
def hook_command(
    commit_msg_file: Path = typer.Argument(
        ...,
        help="Path to the commit message file",
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
        exists=False,
        file_okay=True,
        dir_okay=False,
        resolve_path=True,
    ),
    version_file: Optional[Path] = typer.Option(
        None,
        "--version-file",
        "-v",
        help="Path to version file (overrides config)",
        exists=False,
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
    """Process a commit message file for version bumping.

    This command is intended to be used as a git hook to automatically
    update version numbers based on conventional commit messages.

    Can be used as either prepare-commit-msg or commit-msg hook.
    When used as prepare-commit-msg, Git provides additional arguments
    that enable reliable amend detection.
    """
    # Import and call the pre_commit module directly to use the modern multi-file system
    from ..hooks.pre_commit import main as pre_commit_main

    try:
        # Call the pre_commit main function with the provided arguments
        pre_commit_main(
            commit_msg_file=commit_msg_file,
            commit_source=commit_source,
            commit_sha=commit_sha,
            config_file=config_file,
            version_file=version_file,
            skip_amend_detection=skip_amend_detection,
        )

    except typer.Exit:
        # Re-raise typer.Exit exceptions as-is (they have their own exit codes)
        raise
    except Exception as e:
        console.print(f"[red]Hook failed:[/] {e}")
        raise typer.Exit(1) from e


@app.command(name="install-hooks")
def install_hooks_command(
    config_file: Optional[Path] = typer.Option(
        None,
        "--config",
        "-c",
        help="Configuration file to reference in hooks",
        exists=True,
        file_okay=True,
        dir_okay=False,
        resolve_path=True,
    ),
    create_tag: bool = typer.Option(
        True,
        "--create-tag/--no-create-tag",
        help="Enable automatic git tag creation in post-commit hook",
    ),
    legacy_mode: bool = typer.Option(
        False,
        "--legacy/--modern",
        help="Use legacy commit-msg hook instead of prepare-commit-msg + post-commit",
    ),
) -> None:
    """Install Pezin Git hooks for automatic version management."""
    hooks.install_hooks(config_file, create_tag, legacy_mode)


@app.command(name="uninstall-hooks")
def uninstall_hooks_command() -> None:
    """Uninstall Pezin Git hooks."""
    hooks.uninstall_hooks()


@app.command(name="hooks-status")
def hooks_status_command() -> None:
    """Show status of Pezin Git hooks."""
    hooks.status_hooks()


def run() -> None:
    """Run the CLI application."""
    app()


if __name__ == "__main__":
    run()
