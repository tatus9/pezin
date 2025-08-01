"""Command implementations for pezin CLI."""

from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import tomli
import tomli_w

from ..core.changelog import ChangelogConfig, ChangelogManager
from ..core.commit import ConventionalCommit
from ..core.version import Version, VersionBumpType, VersionFileConfig, VersionManager
from ..logging import get_logger

logger = get_logger()


def resolve_path(path: Path, base_dir: Optional[Path] = None) -> Path:
    """Resolve a path relative to a base directory."""
    if path.is_absolute():
        return path
    if base_dir is None:
        base_dir = Path.cwd()
    elif base_dir.is_file():
        base_dir = base_dir.parent
    resolved = (base_dir / path).resolve()
    logger.debug(f"Resolved path {path} relative to {base_dir} -> {resolved}")
    return resolved


def read_toml_file(file_path: Path) -> Dict[str, Any]:
    """Read and parse a TOML file."""
    try:
        if not file_path.is_file():
            logger.debug(f"TOML file not found: {file_path}")
            return {}
        content = file_path.read_text()
        logger.debug(f"Reading TOML from {file_path}:\n{content}")
        return tomli.loads(content)
    except Exception as e:
        logger.debug(f"Failed to read TOML file {file_path}: {e}")
        return {}


def read_config(config_file: Path) -> Dict[str, Any]:
    """Read configuration from a TOML file."""
    if config_file.suffix != ".toml":
        return {}

    config = read_toml_file(config_file)
    base_dir = config_file.parent

    # Initialize pezin section if needed - check both locations
    pezin_config = {}
    if "pezin" in config:
        pezin_config = config["pezin"]
    elif "tool" in config and "pezin" in config["tool"]:
        pezin_config = config["tool"]["pezin"]

    # Ensure pezin section exists in the expected location
    config["pezin"] = pezin_config

    # Make paths absolute
    if config["pezin"]:
        # Handle legacy single version_file configuration
        if "version_file" in config["pezin"]:
            version_path = Path(config["pezin"]["version_file"])
            if not version_path.is_absolute():
                abs_path = resolve_path(version_path, base_dir)
                logger.debug(
                    f"Making version_file path absolute: {version_path} -> {abs_path}"
                )
                config["pezin"]["version_file"] = str(abs_path)

        # Handle new multi-file version_files configuration
        if "version_files" in config["pezin"]:
            version_files = config["pezin"]["version_files"]
            for i, file_config in enumerate(version_files):
                if isinstance(file_config, dict) and "path" in file_config:
                    file_path = Path(file_config["path"])
                    if not file_path.is_absolute():
                        abs_path = resolve_path(file_path, base_dir)
                        logger.debug(
                            f"Making version_files[{i}] path absolute: {file_path} -> {abs_path}"
                        )
                        config["pezin"]["version_files"][i]["path"] = str(abs_path)

        if "changelog_file" in config["pezin"]:
            changelog_path = Path(config["pezin"]["changelog_file"])
            if not changelog_path.is_absolute():
                abs_path = resolve_path(changelog_path, base_dir)
                logger.debug(
                    f"Making changelog_file path absolute: {changelog_path} -> {abs_path}"
                )
                config["pezin"]["changelog_file"] = str(abs_path)

    return config


def read_version_from_toml(file_path: Path) -> Optional[str]:
    """Read version from TOML file sections."""
    logger.debug(f"Reading version from TOML file: {file_path}")
    data = read_toml_file(file_path)

    # Try project section first
    if "project" in data and "version" in data["project"]:
        return _extract_version_from_section(
            data, "project", "Found version in [project] section: "
        )
    # Try pezin section next
    if "pezin" in data and "version" in data["pezin"]:
        return _extract_version_from_section(
            data, "pezin", "Found version in [pezin] section: "
        )
    # Try tool.pezin section (PEP 518)
    if (
        "tool" in data
        and "pezin" in data["tool"]
        and "version" in data["tool"]["pezin"]
    ):
        version = data["tool"]["pezin"]["version"]
        logger.debug(f"Found version in [tool.pezin] section: {version}")
        return version

    logger.debug("No version found in TOML file")
    return None


def _extract_version_from_section(data, section_name, debug_prefix):
    """Extract version from a specific section with debug logging."""
    version = data[section_name]["version"]
    logger.debug(f"{debug_prefix}{version}")
    return version


def write_toml_version(file_path: Path, new_version: str) -> None:
    """Write version to a TOML file."""
    try:
        data = read_toml_file(file_path)

        # Update in existing location if found
        if "project" in data and "version" in data["project"]:
            data["project"]["version"] = new_version
        elif "pezin" in data and "version" in data["pezin"]:
            data["pezin"]["version"] = new_version
        elif (
            "tool" in data
            and "pezin" in data["tool"]
            and "version" in data["tool"]["pezin"]
        ):
            data["tool"]["pezin"]["version"] = new_version
        else:
            # Default to project section
            if "project" not in data:
                data["project"] = {}
            data["project"]["version"] = new_version

        file_path.write_text(tomli_w.dumps(data))
    except Exception as e:
        raise ValueError(f"Failed to write TOML file: {e}") from e


def read_raw_version(file_path: Path) -> Optional[str]:
    """Read version from a raw version file."""
    if not file_path.is_file():
        return None
    content = file_path.read_text().strip()
    if len(content.splitlines()) == 1:
        Version.parse(content)  # Validate version string
        return content


def get_version_info(
    config_file: Path, config: Optional[Dict[str, Any]] = None
) -> Tuple[str, Path]:
    """Get version information from config or file (legacy function)."""
    if config is None:
        config = read_config(config_file)

    config_file = config_file.resolve()
    logger.debug(f"Getting version info from {config_file} with config: {config}")

    # First try reading version from config file if it's TOML
    if config_file.suffix == ".toml":
        if version := read_version_from_toml(config_file):
            return version, config_file

    # Check for external version file
    if "pezin" in config and "version_file" in config["pezin"]:
        version_file = Path(config["pezin"]["version_file"])
        version_file = resolve_path(version_file, config_file.parent)
    else:
        version_file = config_file

    logger.debug(f"Checking version file: {version_file}")

    # Try reading from version file
    if version_file.suffix == ".toml":
        if version := read_version_from_toml(version_file):
            return version, version_file

    if version := read_raw_version(version_file):
        return version, version_file

    if not version_file.exists():
        raise FileNotFoundError(f"Version file not found: {version_file}")

    raise ValueError(f"Version not found in {version_file}")


def get_version_manager(
    config_file: Path, config: Optional[dict] = None
) -> VersionManager:
    """Get VersionManager instance from configuration."""
    if config is None:
        config = read_config(config_file)

    # Check if we have new multi-file configuration
    if config and "pezin" in config and "version_files" in config["pezin"]:
        return VersionManager.from_config(config["pezin"])

    # Create manager from legacy configuration
    if config and "pezin" in config and "version_file" in config["pezin"]:
        version_file = config["pezin"]["version_file"]
    else:
        version_file = str(config_file)

    return VersionManager([VersionFileConfig(path=version_file)])


def get_current_version(
    config_file: Path, config: Optional[dict] = None
) -> Optional[str]:
    """Get current version using the new VersionManager system."""
    try:
        version_manager = get_version_manager(config_file, config)
        version = version_manager.get_primary_version()
        return str(version) if version else None
    except Exception as e:
        logger.error(f"Failed to get current version: {e}")
        return None


def write_version_to_file(
    file_path: Path, new_version: str, config: Optional[dict] = None
) -> None:
    """Write version to a file."""
    file_path = file_path.resolve()
    logger.debug(f"Writing version {new_version} to {file_path}")

    # Create parent directories if needed
    file_path.parent.mkdir(parents=True, exist_ok=True)

    # Write version based on file type
    if file_path.suffix == ".toml":
        write_toml_version(file_path, new_version)
    else:
        file_path.write_text(new_version)


def get_changelog_file(config: Dict[str, Any], default_file: Path) -> Path:
    """Get changelog file path from config or default."""
    if "pezin" in config and "changelog_file" in config["pezin"]:
        return Path(config["pezin"]["changelog_file"])
    return default_file


_git_repo_url_cache = None


def get_git_repo_url() -> Optional[str]:
    """Get repository URL from git config (cached)."""
    global _git_repo_url_cache

    if _git_repo_url_cache is not None:
        return _git_repo_url_cache

    import subprocess

    try:
        result = subprocess.run(
            ["git", "config", "--get", "remote.origin.url"],
            capture_output=True,
            text=True,
            check=True,
        )
        url = result.stdout.strip()

        # Convert SSH to HTTPS URL if needed
        if url.startswith("git@"):
            url = url.replace(":", "/").replace("git@", "https://")

        if url.endswith(".git"):
            url = url[:-4]

        _git_repo_url_cache = url
        return url

    except subprocess.CalledProcessError:
        _git_repo_url_cache = None
        return None


_commits_cache = None
_last_head_sha = None


def get_commits_since_last_tag() -> List[ConventionalCommit]:
    """Get commits since the last version tag (cached)."""
    global _commits_cache, _last_head_sha

    import subprocess

    try:
        # Check current HEAD to see if cache is still valid
        current_head = subprocess.run(
            ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True
        ).stdout.strip()

        if _commits_cache is not None and _last_head_sha == current_head:
            return _commits_cache

        commits = []
        get_commits_from_logs(subprocess, commits)

        # Cache the results
        _commits_cache = commits
        _last_head_sha = current_head

        return commits

    except subprocess.CalledProcessError:
        logger.debug("Not in a git repository or no commits found")
        return []


def get_commits_from_logs(subprocess, commits):
    # Check if in a git repo first
    subprocess.run(["git", "rev-parse", "--git-dir"], capture_output=True, check=True)

    # Try to get last tag
    result = subprocess.run(
        ["git", "describe", "--tags", "--abbrev=0"],
        capture_output=True,
        text=True,
        check=False,
    )

    # Build git log command
    log_cmd = ["git", "log", "--pretty=format:%B%n<<>>%n"]
    if result.returncode == 0:
        log_cmd.extend([f"{result.stdout.strip()}..HEAD"])

    # Get and parse commits
    log_output = subprocess.run(log_cmd, capture_output=True, text=True, check=True)

    for message in log_output.stdout.split("<<>>\n"):
        if message.strip():
            try:
                commits.append(ConventionalCommit.parse(message.strip()))
            except ValueError:
                continue


def bump_version(
    bump_type: VersionBumpType,
    config_file: Path,
    config: Optional[dict] = None,
    dry_run: bool = False,
    prerelease: Optional[str] = None,
) -> Optional[str]:
    """Bump version in config file and all configured version files."""
    try:
        # Read config if not provided
        if config is None and config_file.suffix == ".toml":
            config = read_config(config_file)

        logger.debug(f"Bumping version with config: {config}")

        if config and "pezin" in config and "version_files" in config["pezin"]:
            return prepare_new_version(config, bump_type, prerelease, dry_run)
        # Fallback to legacy single file logic
        current, version_file = get_version_info(config_file, config)
        version = Version.parse(current)
        new_version = str(version.bump(bump_type, prerelease))

        if not dry_run:
            write_version_to_file(version_file, new_version)
            logger.info(f"Version bumped: {current} -> {new_version}")
        else:
            logger.info(f"Dry run - Would bump: {current} -> {new_version}")

        return new_version

    except Exception as e:
        logger.error(f"Failed to bump version: {e}")
        return None


def prepare_new_version(config, bump_type, prerelease, dry_run):
    """Prepare new version using VersionManager system."""
    version_manager = VersionManager.from_config(config["pezin"])

    current_version = version_manager.get_primary_version()
    if not current_version:
        raise ValueError("No version found in configured files")

    if not version_manager.validate_version_consistency():
        logger.warning("Version inconsistency detected across files")

    new_version = current_version.bump(bump_type, prerelease)

    if not dry_run:
        updated_files = version_manager.write_versions(new_version)
        logger.info(f"Version bumped: {current_version} -> {new_version}")
        logger.info(f"Updated files: {', '.join(updated_files)}")
    else:
        versions = version_manager.read_versions()
        logger.info(f"Dry run - Would bump: {current_version} -> {new_version}")
        logger.info(f"Files to update: {', '.join(versions.keys())}")

    return str(new_version)


def update_changelog(
    version: str,
    commits: List[ConventionalCommit],
    changelog_file: Path = Path("CHANGELOG.md"),
    dry_run: bool = False,
    config: Optional[dict] = None,
) -> bool:
    """Update changelog with new version."""
    try:
        # Get actual changelog file path
        actual_file = get_changelog_file(config or {}, changelog_file)
        actual_file = resolve_path(actual_file)

        logger.debug(f"Using changelog file: {actual_file}")

        # Create changelog file if it doesn't exist
        if not dry_run:
            actual_file.parent.mkdir(parents=True, exist_ok=True)
            if not actual_file.exists():
                actual_file.write_text("# Changelog\n\n## [Unreleased]\n")

        manager_config = ChangelogConfig(repo_url=get_git_repo_url())
        manager = ChangelogManager(manager_config)

        if not dry_run:
            manager.update_changelog(actual_file, version, commits, datetime.now())
            logger.info(f"Updated changelog for version {version}")
        else:
            logger.info(f"Dry run - Would update changelog for version {version}")

        return True

    except Exception as e:
        logger.error(f"Failed to update changelog: {e}")
        return False
