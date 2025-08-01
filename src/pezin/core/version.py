"""Version management utilities.

This module provides classes and functions for handling semantic versioning
and conventional commits. Uses the `packaging` library for robust version parsing.

Example:
    ```python
    # Parse version string
    version = Version.parse("1.2.3-beta+build.123")

    # Bump version
    new_version = version.bump(VersionBumpType.MINOR)

    # Parse commit message
    commit = ConventionalCommit.parse(
        "feat(auth)!: redesign authentication system\n\nBREAKING CHANGE: new API"
    )
    bump_type = commit.get_bump_type()  # Returns VersionBumpType.MAJOR
    ```
"""

import re
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

from packaging.version import Version as PackagingVersion

from ..logging import get_logger

logger = get_logger()


class VersionBumpType(str, Enum):
    """Type of version bump following semantic versioning."""

    MAJOR = "major"
    MINOR = "minor"
    PATCH = "patch"


class Version:
    """Semantic version handling with custom formatting support."""

    def __init__(
        self,
        version_string: Optional[str] = None,
        major: Optional[int] = None,
        minor: Optional[int] = None,
        patch: Optional[int] = None,
        prerelease: Optional[str] = None,
        build: Optional[str] = None,
        original_format: Optional[str] = None,
    ):
        """Initialize Version from string or components."""
        if version_string is not None:
            # Parse from string (existing behavior)
            self._init_from_string(version_string)
        elif major is not None and minor is not None and patch is not None:
            # Parse from components (new behavior)
            self._init_from_components(
                major, minor, patch, prerelease, build, original_format
            )
        else:
            raise ValueError(
                "Either version_string or major/minor/patch components must be provided"
            )

    def _init_from_string(self, version_string: str):
        """Initialize from a version string (original behavior)."""
        # Extract semantic version core using regex
        version_pattern = r"(?:^|[^\d])(\d+)\.(\d+)\.(\d+)(?:-([a-zA-Z0-9\-]+))?(?:\+([a-zA-Z0-9\-\.]+))?(?:[^\d]|$)"
        if match := re.search(version_pattern, version_string):
            self._define_version_original_format(match, version_string)
        else:
            # Fallback to old behavior for simple cases
            clean_version = version_string.lstrip("vV")
            prefix = version_string[: len(version_string) - len(clean_version)]

            self._version = PackagingVersion(clean_version)
            self._original_format = (
                prefix + "{major}.{minor}.{patch}" if prefix else None
            )

    def _define_version_original_format(self, match, version_string):
        major, minor, patch, prerelease, build = match.groups()

        # Build clean semantic version
        clean_version = f"{major}.{minor}.{patch}"
        if prerelease:
            clean_version += f"-{prerelease}"
        if build:
            clean_version += f"+{build}"

        self._version = PackagingVersion(clean_version)

        # Create format template based on original string
        prefix = version_string[: match.start(1)]
        suffix = version_string[match.end(3) :]

        if build:
            suffix = version_string[match.end(5) :]
        elif prerelease:
            suffix = version_string[match.end(4) :]

        format_template = f"{prefix}{{major}}.{{minor}}.{{patch}}"
        if prerelease:
            format_template += "-{prerelease}"
        if build:
            format_template += "+{build}"
        format_template += suffix

        self._original_format = format_template if (prefix or suffix) else None

    def _init_from_components(
        self,
        major: int,
        minor: int,
        patch: int,
        prerelease: Optional[str] = None,
        build: Optional[str] = None,
        original_format: Optional[str] = None,
    ):
        """Initialize from individual components (new behavior)."""
        # Build version string from components
        version_str = f"{major}.{minor}.{patch}"
        if prerelease:
            version_str += f"-{prerelease}"
        if build:
            version_str += f"+{build}"

        self._version = PackagingVersion(version_str)
        self._original_format = original_format

    @property
    def major(self) -> int:
        """Major version number."""
        return self._version.major

    @property
    def minor(self) -> int:
        """Minor version number."""
        return self._version.minor

    @property
    def patch(self) -> int:
        """Patch version number."""
        return self._version.micro

    @property
    def prerelease(self) -> Optional[str]:
        """Pre-release identifier if any."""
        if self._version.pre:
            return {"a": "alpha", "b": "beta", "rc": "rc"}.get(
                self._version.pre[0], self._version.pre[0]
            )
        return None

    @property
    def build(self) -> Optional[str]:
        """Build metadata if any."""
        return self._version.local or None

    def format_with_template(self, template: str) -> str:
        """Format version using template with placeholders like {version}, {major}, {date}."""
        now = datetime.now()

        # Build full semantic version string
        version_str = f"{self.major}.{self.minor}.{self.patch}"
        if self.prerelease:
            version_str += f"-{self.prerelease}"
        if self.build:
            version_str += f"+{self.build}"

        # Template variables
        variables = {
            "version": version_str,
            "major": self.major,
            "minor": self.minor,
            "patch": self.patch,
            "major_padded": f"{self.major:03d}",
            "minor_padded": f"{self.minor:03d}",
            "patch_padded": f"{self.patch:03d}",
            "prerelease": self.prerelease or "",
            "build": self.build or "",
            "date": now.strftime("%Y-%m-%d"),
            "year": now.strftime("%Y"),
            "month": now.strftime("%m"),
            "day": now.strftime("%d"),
            "timestamp": str(int(now.timestamp())),
        }

        return template.format(**variables)

    @classmethod
    def from_components(
        cls,
        major: int,
        minor: int,
        patch: int,
        prerelease: Optional[str] = None,
        build: Optional[str] = None,
        original_format: Optional[str] = None,
    ) -> "Version":
        """Create Version from major.minor.patch components."""
        return cls(
            major=major,
            minor=minor,
            patch=patch,
            prerelease=prerelease,
            build=build,
            original_format=original_format,
        )

    @classmethod
    def parse_components(
        cls, version_parts: Tuple[str, ...], original_format: Optional[str] = None
    ) -> "Version":
        """Parse version from tuple of component strings.

        Args:
            version_parts: Tuple containing (major, minor, patch) or (major, minor, patch, prerelease)
            original_format: Original formatting pattern to preserve

        Returns:
            Version: New Version instance

        Raises:
            ValueError: If version_parts doesn't contain valid components
        """
        if len(version_parts) < 3:
            raise ValueError(
                "version_parts must contain at least (major, minor, patch)"
            )

        try:
            major = int(version_parts[0])
            minor = int(version_parts[1])
            patch = int(version_parts[2])
            prerelease = version_parts[3] if len(version_parts) > 3 else None

            return cls.from_components(
                major, minor, patch, prerelease, original_format=original_format
            )
        except (ValueError, IndexError) as e:
            raise ValueError(f"Invalid version components: {version_parts}") from e

    @classmethod
    def parse(cls, version_str: str) -> "Version":
        """Parse a version string into a Version object.

        Args:
            version_str: String in semver format (X.Y.Z[-pre][+build])

        Returns:
            Version: New Version instance

        Raises:
            InvalidVersion: If version string is not valid
        """
        return cls(version_str)

    def __str__(self) -> str:
        """Convert to string representation.

        Uses original format template if available, otherwise falls back to SemVer format
        with preserved prefix (like 'v') if it was present in the input.
        """
        # Use original format template if available
        if self._original_format:
            return self.format_with_template(self._original_format)

        # Fallback to standard SemVer format with original prefix
        version = f"{self.major}.{self.minor}.{self.patch}"

        if self._version.pre:
            if pre_type := {"a": "alpha", "b": "beta", "rc": "rc"}.get(
                self._version.pre[0]
            ):
                version += f"-{pre_type}"

        if self.build:
            version += f"+{self.build}"

        return version

    def bump(
        self, bump_type: VersionBumpType, prerelease: Optional[str] = None
    ) -> "Version":
        """Create a new Version with bumped version numbers.

        Args:
            bump_type: Type of version bump to perform
            prerelease: Optional pre-release label for new version

        Returns:
            Version: New Version instance with updated numbers
        """

        major = self.major
        minor = self.minor
        patch = self.patch

        if bump_type is not None:
            if bump_type == VersionBumpType.MAJOR:
                major += 1
                minor = 0
                patch = 0
            elif bump_type == VersionBumpType.MINOR:
                minor += 1
                patch = 0
            else:  # PATCH
                patch += 1

        version_str = f"{major}.{minor}.{patch}"
        if prerelease:
            version_str += f"-{prerelease}"
        if self.build:
            version_str += f"+{self.build}"

        # Preserve the original format when creating the new version
        return Version.from_components(
            major, minor, patch, prerelease, self.build, self._original_format
        )


def parse_version(version_str: str) -> Version:
    """Parse a version string into a Version object."""
    return Version.parse(version_str)


def bump_version(current: str, bump_type: VersionBumpType) -> str:
    """Bump the version according to semver rules."""
    version = Version.parse(current)
    return str(version.bump(bump_type))


@dataclass
class VersionFileConfig:
    """Configuration for a version file."""

    path: Union[str, Path]
    file_type: Optional[str] = None
    version_key: Optional[str] = None
    version_pattern: Optional[str] = None
    version_replacement: Optional[str] = None
    version_format: Optional[str] = None  # New: template for output formatting
    encoding: str = "utf-8"


class VersionManager:
    """Manages version updates across multiple files."""

    def __init__(self, config_files: List[VersionFileConfig]):
        self.config_files = config_files
        self._handlers = {}
        self._setup_handlers()

    def _setup_handlers(self):
        """Initialize file handlers for each configured file."""
        # Import here to avoid circular imports
        from .handlers import FileHandlerFactory

        for config in self.config_files:
            handler_kwargs = {}

            if config.version_key:
                handler_kwargs["version_key"] = config.version_key
            if config.version_pattern:
                handler_kwargs["version_pattern"] = config.version_pattern
            if config.version_replacement:
                handler_kwargs["version_replacement"] = config.version_replacement
            if config.version_format:
                handler_kwargs["version_format"] = config.version_format
            if config.encoding != "utf-8":
                handler_kwargs["encoding"] = config.encoding

            handler = FileHandlerFactory.create_handler(
                config.path, config.file_type, **handler_kwargs
            )
            self._handlers[str(config.path)] = handler

    def read_versions(self) -> Dict[str, Optional[Version]]:
        """Read versions from all configured files."""
        versions = {}
        for path, handler in self._handlers.items():
            try:
                version = handler.read_version()
                versions[path] = version
            except Exception as e:
                logger.warning(f"Could not read version from {path}: {e}")
                versions[path] = None
        return versions

    def write_versions(self, version: Version) -> List[str]:
        """Write version to all configured files."""
        updated_files = []
        for path, handler in self._handlers.items():
            try:
                handler.write_version(version)
                updated_files.append(path)
            except Exception as e:
                logger.warning(f"Could not write version to {path}: {e}")
        return updated_files

    def get_primary_version(self) -> Optional[Version]:
        """Get version from the first configured file."""
        if not self.config_files:
            return None

        if handler := self._handlers.get(str(self.config_files[0].path)):
            return handler.read_version()
        return None

    def validate_version_consistency(self) -> bool:
        """Check if all files have the same version."""
        versions = self.read_versions()
        valid_versions = [v for v in versions.values() if v is not None]

        if not valid_versions:
            return True

        first_version = str(valid_versions[0])
        return all(str(v) == first_version for v in valid_versions)

    @classmethod
    def from_config(cls, config: Dict) -> "VersionManager":
        """Create VersionManager from configuration dictionary."""
        version_files = config.get("version_files", [])

        if not version_files:
            # Fallback to legacy single file configuration
            version_file = config.get("version_file", "pyproject.toml")
            version_files = [{"path": version_file}]

        configs = []
        for file_config in version_files:
            if isinstance(file_config, str):
                # Simple path string
                configs.append(VersionFileConfig(path=file_config))
            else:
                # Full configuration object
                configs.append(VersionFileConfig(**file_config))

        return cls(configs)
