"""CLI commands for managing Git hooks."""

import stat
import subprocess
from pathlib import Path
from typing import Optional

import typer

from ..logging import get_logger

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
        raise typer.Exit(1) from e


def get_git_hooks_dir() -> Path:
    """Get the Git hooks directory."""
    repo_root = get_repo_root()
    try:
        git_dir_str = subprocess.check_output(
            ["git", "-C", str(repo_root), "rev-parse", "--git-dir"], text=True
        ).strip()
        git_dir = (
            Path(git_dir_str)
            if Path(git_dir_str).is_absolute()
            else (repo_root / git_dir_str).resolve()
        )
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to determine git directory: {e}")
        raise typer.Exit(1) from e

    hooks_dir = git_dir / "hooks"
    hooks_dir.mkdir(exist_ok=True)
    return hooks_dir


def create_hook_script(hook_name: str, python_module: str, hooks_dir: Path) -> Path:
    """Create a Git hook script that calls the appropriate Python module."""
    hook_path = hooks_dir / hook_name

    # Create the hook script
    script_content = f"""#!/usr/bin/env python3
\"\"\"
Git {hook_name} hook managed by Pezin.
This file is auto-generated. Do not edit manually.
\"\"\"

import sys
from pathlib import Path

# Add the pezin package to Python path if needed
try:
    import pezin
except ImportError:
    # Try to find pezin in common locations
    current_dir = Path(__file__).parent
    repo_root = current_dir.parent.parent
    possible_paths = [
        repo_root / "src",
        repo_root,
        Path.cwd() / "src",
        Path.cwd(),
    ]

    for path in possible_paths:
        if (path / "pezin").exists():
            sys.path.insert(0, str(path))
            break
    else:
        print("Error: Could not find pezin package", file=sys.stderr)
        sys.exit(1)

# Import and run the hook
try:
    from {python_module} import main
    main()
except Exception as e:
    print(f"Error running {hook_name} hook: {{e}}", file=sys.stderr)
    import traceback
    traceback.print_exc()
    sys.exit(1)
"""

    hook_path.write_text(script_content)

    # Make the hook executable
    hook_path.chmod(
        hook_path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH
    )

    logger.info(f"Created {hook_name} hook: {hook_path}")
    return hook_path


def install_hooks(
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
    """Install Pezin Git hooks for automatic version management.

    This installs hooks that automatically bump versions and create tags
    based on conventional commit messages.

    Two modes available:
    - Modern (default): prepare-commit-msg + post-commit hooks with automatic amendment
    - Legacy: commit-msg hook with staged files (backward compatible)
    """
    try:
        hooks_dir = get_git_hooks_dir()

        typer.echo(f"Installing Pezin hooks in: {hooks_dir}")

        if legacy_mode:
            # Install legacy commit-msg hook
            create_hook_script("commit-msg", "pezin.hooks.pre_commit", hooks_dir)
            typer.echo("✓ Installed commit-msg hook (legacy mode)")
            typer.echo("  → Version files will be staged for manual commit")

        else:
            # Install modern hook system

            # 1. Install prepare-commit-msg hook for amend detection
            create_hook_script(
                "prepare-commit-msg", "pezin.hooks.prepare_commit_msg", hooks_dir
            )
            typer.echo("✓ Installed prepare-commit-msg hook")
            typer.echo("  → Validates commit format and detects amends")

            # 2. Install post-commit hook for version bumping and tagging
            create_hook_script("post-commit", "pezin.hooks.post_commit", hooks_dir)
            typer.echo("✓ Installed post-commit hook")
            typer.echo("  → Automatically amends commits with version changes")
            if create_tag:
                typer.echo("  → Creates git tags for new versions")

        # Create a marker file to indicate hooks are managed by Pezin
        marker_file = hooks_dir / ".pezin-managed"
        marker_content = f"""# Pezin-managed hooks
# Created: {typer.get_app_dir("pezin")}
# Mode: {"legacy" if legacy_mode else "modern"}
# Config: {config_file or "auto-detect"}
# Create tags: {create_tag}
"""
        marker_file.write_text(marker_content)

        typer.echo("\n🎉 Pezin hooks installed successfully!")

        if not legacy_mode:
            typer.echo("\nHow it works:")
            typer.echo("1. Write conventional commit messages (feat:, fix:, etc.)")
            typer.echo("2. Commit normally - hooks detect version bump needed")
            typer.echo(
                "3. Version files are updated and commit is automatically amended"
            )
            typer.echo("4. Git tag is created for the new version")
            typer.echo("\nNo more staged files or manual amendments needed! 🚀")
        else:
            typer.echo(
                "\nLegacy mode: Remember to re-commit after version files are staged."
            )

    except (OSError, subprocess.CalledProcessError) as e:
        logger.error(f"Failed to install hooks: {e}", exc_info=True)
        typer.echo(f"❌ Error installing hooks: {e}", err=True)
        raise typer.Exit(1) from e
    except Exception as e:
        logger.error(f"Unexpected error during hook installation: {e}", exc_info=True)
        typer.echo(f"❌ Unexpected error installing hooks: {e}", err=True)
        raise typer.Exit(1) from e


def uninstall_hooks() -> None:
    """Uninstall Pezin Git hooks.

    Removes all Pezin-managed Git hooks and cleans up related files.
    """
    try:
        hooks_dir = get_git_hooks_dir()

        # Remove hooks
        hooks_to_remove = ["commit-msg", "prepare-commit-msg", "post-commit"]
        removed = []

        for hook_name in hooks_to_remove:
            hook_path = hooks_dir / hook_name
            if hook_path.exists():
                # Check if it's a Pezin-managed hook
                try:
                    content = hook_path.read_text()
                    if "pezin" in content.lower() and "auto-generated" in content:
                        hook_path.unlink()
                        removed.append(hook_name)
                        logger.info(f"Removed {hook_name} hook")
                    else:
                        typer.echo(f"⚠️  Skipping {hook_name} (not managed by Pezin)")
                except Exception as e:
                    logger.warning(f"Could not check {hook_name}: {e}")

        # Remove marker file
        marker_file = hooks_dir / ".pezin-managed"
        if marker_file.exists():
            marker_file.unlink()
            logger.info("Removed Pezin marker file")

        # Remove lock file if present
        repo_root = get_repo_root()
        lock_file = repo_root / ".pezin_post_commit_lock"
        if lock_file.exists():
            lock_file.unlink()
            logger.info("Removed lock file")

        if removed:
            typer.echo(f"✓ Removed hooks: {', '.join(removed)}")
            typer.echo("🧹 Pezin hooks uninstalled successfully!")
        else:
            typer.echo("No Pezin hooks found to remove.")

    except Exception as e:
        logger.error(f"Failed to uninstall hooks: {e}")
        typer.echo(f"❌ Error uninstalling hooks: {e}", err=True)
        raise typer.Exit(1) from e


def status_hooks() -> None:
    """Show status of Pezin Git hooks.

    Displays information about currently installed hooks and their configuration.
    """
    try:
        check_and_determine_status_hooks()
    except Exception as e:
        logger.error(f"Failed to check hook status: {e}")
        typer.echo(f"❌ Error checking hooks: {e}", err=True)
        raise typer.Exit(1) from e


def check_and_determine_status_hooks():
    hooks_dir = get_git_hooks_dir()
    repo_root = get_repo_root()

    typer.echo(f"Git hooks directory: {hooks_dir}")
    typer.echo(f"Repository root: {repo_root}")

    # Check for marker file
    marker_file = hooks_dir / ".pezin-managed"
    if marker_file.exists():
        typer.echo("\n📋 Pezin hooks configuration:")
        typer.echo(marker_file.read_text())
    else:
        typer.echo("\n⚠️  No Pezin marker file found")

    # Check individual hooks
    hooks_to_check = ["commit-msg", "prepare-commit-msg", "post-commit"]
    typer.echo("\n🔍 Hook status:")

    pezin_hooks = []
    for hook_name in hooks_to_check:
        hook_path = hooks_dir / hook_name
        if hook_path.exists():
            try:
                content = hook_path.read_text()
                if "pezin" in content.lower():
                    pezin_hooks.append(hook_name)
                    typer.echo(f"  ✓ {hook_name} (Pezin-managed)")
                else:
                    typer.echo(f"  ⚠️  {hook_name} (external)")
            except Exception:
                typer.echo(f"  ❓ {hook_name} (unreadable)")
        else:
            typer.echo(f"  ✗ {hook_name} (not installed)")

    # Check for lock file
    lock_file = repo_root / ".pezin_post_commit_lock"
    if lock_file.exists():
        typer.echo(f"\n🔒 Lock file present: {lock_file}")
        typer.echo("  (This may indicate a stuck process)")

    # Determine mode
    if "prepare-commit-msg" in pezin_hooks and "post-commit" in pezin_hooks:
        typer.echo("\n🚀 Mode: Modern (prepare-commit-msg + post-commit)")
    elif "commit-msg" in pezin_hooks:
        typer.echo("\n🔄 Mode: Legacy (commit-msg)")
    elif pezin_hooks:
        typer.echo("\n⚠️  Mode: Partial installation")
    else:
        typer.echo("\n❌ Mode: Not installed")
