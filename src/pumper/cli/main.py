"""CLI entry point for pumper tool."""

import subprocess
from pathlib import Path
from typing import List, Optional

import tomli
import tomli_w
import typer
from rich.console import Console

from ..core.version import VersionBumpType, Version, ConventionalCommit
from . import commands
from . import utils
from ..logging import setup_logging, get_logger

# Set up centralized logging
setup_logging()
logger = get_logger()

# Initialize Typer app and console
app = typer.Typer(
    help="Version management and changelog tool for semantic versioning",
    add_completion=False,
    no_args_is_help=True,
)

console = Console()


def validate_prerelease(value: Optional[str]) -> Optional[str]:
    """Validate pre-release label."""
    if value is not None and value not in ["alpha", "beta", "rc"]:
        raise typer.BadParameter("Must be one of: alpha, beta, rc")
    return value


def _is_amend_commit(commit_message: str) -> bool:
    """Check if the current commit is an amend operation."""
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

        except (subprocess.CalledProcessError, FileNotFoundError, OSError):
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
        except FileNotFoundError as e:
            console.print(f"[red]Error:[/] {str(e)}")
            raise typer.Exit(1)
        except ValueError as e:
            console.print(f"[red]Error:[/] {str(e)}")
            raise typer.Exit(1)

        # Get commits
        commits = []
        if message:
            for msg in message:
                try:
                    commits.append(commands.ConventionalCommit.parse(msg))
                except ValueError:
                    console.print(f"[red]Error:[/] Invalid commit message: {msg}")
                    raise typer.Exit(1)
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
        raise typer.Exit(1)


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
) -> None:
    """Process a commit message file for version bumping.

    This command is intended to be used as a git hook to automatically
    update version numbers based on conventional commit messages.
    """
    try:
        # Read commit message
        message = commit_msg_file.read_text().strip()
        if not message:
            console.print("[yellow]Warning:[/] Empty commit message")
            raise typer.Exit(0)

        # Check if this is an amend commit
        if _is_amend_commit(message):
            console.print("[yellow]Amend commit detected - skipping version bump[/]")
            raise typer.Exit(0)

        # Process commit message
        try:
            commit = ConventionalCommit.parse(message)
            console.print(f"Commit type: {commit.type}")

            bump_type = commit.get_bump_type()
            console.print(f"Bump type: {bump_type}")

            if bump_type is None:
                console.print("[yellow]No version bump needed[/]")
                raise typer.Exit(0)

            # Find version file (look for pyproject.toml in repo root)
            repo_root = utils.find_project_root()
            if commit_msg_file.is_absolute():
                # If we're given an absolute path (like in tests), use the parent directory
                repo_root = utils.find_project_root(
                    current_path=Path(commit_msg_file.parent)
                )
            console.print(f"Repository root: {repo_root}")
            version_file = repo_root / "pyproject.toml"
            if not version_file.exists():
                console.print(
                    f"[yellow]Warning:[/] Version file not found: {version_file}"
                )
                raise typer.Exit(0)

            # Read current version
            with open(version_file, "rb") as f:
                config = tomli.load(f)
                current = config["project"]["version"]
            console.print(f"Current version: {current}")

            # Process pre-release label
            prerelease = commit.get_prerelease_label()
            console.print(f"Pre-release label: {prerelease}")

            # Get the footer tokens directly for debugging
            footer_tokens = commit.get_footer_tokens()
            console.print(f"Footer tokens: {footer_tokens}")

            # Bump version
            version = Version.parse(current)
            new_version = version.bump(bump_type, prerelease)
            console.print(f"Bumping to: {new_version}")

            # Update version file
            config["project"]["version"] = str(new_version)
            with open(version_file, "wb") as f:
                tomli_w.dump(config, f)

            # Stage version file
            try:
                subprocess.run(
                    ["git", "add", str(version_file)], capture_output=True, check=True
                )
                console.print("[green]Version file staged[/]")
            except Exception as e:
                console.print(f"[yellow]Git staging skipped:[/] {e}")

            console.print(f"[green]✨ Version bumped to {new_version}[/]")

        except ValueError as e:
            console.print(f"[yellow]Warning:[/] {e}")
            # Non-conventional commits are allowed, just don't bump version
            raise typer.Exit(0)

    except typer.Exit:
        # Re-raise typer.Exit exceptions as-is (they have their own exit codes)
        raise
    except Exception as e:
        console.print(f"[red]Hook failed:[/] {e}")
        raise typer.Exit(1)


def run() -> None:
    """Run the CLI application."""
    app()


if __name__ == "__main__":
    run()
