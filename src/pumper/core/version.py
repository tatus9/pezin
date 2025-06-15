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
from enum import Enum
from typing import Optional

from packaging.version import Version as PackagingVersion


class VersionBumpType(str, Enum):
    """Type of version bump to perform.

    This enum defines the different types of version bumps following semver:
    - MAJOR: Breaking changes (incompatible API changes)
    - MINOR: New features (backwards compatible)
    - PATCH: Bug fixes and small changes (backwards compatible)
    """

    MAJOR = "major"
    MINOR = "minor"
    PATCH = "patch"


class CommitType(str, Enum):
    """Valid conventional commit types.

    Supported commit types following conventional commits specification:
    - feat: New feature
    - fix: Bug fix
    - docs: Documentation only changes
    - style: Changes not affecting meaning (formatting)
    - refactor: Neither fixes bug nor adds feature
    - perf: Improves performance
    - test: Adding or updating tests
    - chore: Changes to build process or auxiliary tools
    """

    FEAT = "feat"
    FIX = "fix"
    DOCS = "docs"
    STYLE = "style"
    REFACTOR = "refactor"
    PERF = "perf"
    TEST = "test"
    CHORE = "chore"


@dataclass
class ConventionalCommit:
    """Parser for conventional commit messages.

    This class parses and analyzes commit messages following the Conventional
    Commits specification. It can determine:
    - Commit type (feat, fix, etc.)
    - Optional scope
    - Breaking change indicators
    - Description
    - Optional body text
    - Optional footer with metadata

    Supports:
    - Breaking changes marked with ! or BREAKING CHANGE footer
    - Special command footers ([skip-bump], [force-*], etc.)
    - Pre-release labels
    """

    type: CommitType
    scope: Optional[str]
    breaking: bool
    description: str
    body: Optional[str]
    footer: Optional[str]

    COMMIT_PATTERN = re.compile(
        r"""
        ^(?P<type>feat|fix|docs|style|refactor|perf|test|chore)
        (?:\((?P<scope>[^)]+)\))?
        (?P<breaking>!)?
        :\s
        (?P<description>.+?)
        (?:\n\n(?P<body_and_footer>.+))?$
        """,
        re.VERBOSE | re.DOTALL,
    )

    BREAKING_CHANGE_PATTERN = re.compile(r"BREAKING[\s-]CHANGE:")
    FOOTER_TOKEN_PATTERN = re.compile(r"\[(?P<key>[^=\]]+)(?:=(?P<value>[^\]]+))?\]")

    @classmethod
    def parse(cls, message: str) -> "ConventionalCommit":
        """Parse a commit message into its components.

        Args:
            message: The commit message to parse

        Returns:
            ConventionalCommit: Instance containing parsed components

        Raises:
            ValueError: If message doesn't follow conventional commit format
        """
        match = cls.COMMIT_PATTERN.match(message.strip())
        if not match:
            raise ValueError(
                "Commit message must follow Conventional Commits format:\n"
                "<type>[optional scope]!: <description>\n\n[optional body]\n\n[optional footer]"
            )

        data = match.groupdict()

        # Parse body and footer from combined content
        body_and_footer = data.get("body_and_footer")
        body = None
        footer = None

        if body_and_footer:
            # Check if it contains BREAKING CHANGE or footer tokens
            if cls.BREAKING_CHANGE_PATTERN.search(
                body_and_footer
            ) or cls.FOOTER_TOKEN_PATTERN.search(body_and_footer):
                # If it contains footer patterns, treat as footer
                footer = body_and_footer
            else:
                # Otherwise treat as body
                body = body_and_footer

        breaking = bool(data["breaking"]) or bool(
            footer and cls.BREAKING_CHANGE_PATTERN.search(footer)
        )

        return cls(
            type=CommitType(data["type"]),
            scope=data.get("scope"),
            breaking=breaking,
            description=data["description"],
            body=body,
            footer=footer,
        )

    def get_bump_type(self) -> Optional[VersionBumpType]:
        """Determine version bump type from commit message."""
        # Check both body and footer for control flags
        content_to_check = []
        if self.body:
            content_to_check.append(self.body)
        if self.footer:
            content_to_check.append(self.footer)

        # Check for skip-bump in both body and footer
        for content in content_to_check:
            if "[skip-bump]" in content:
                return None

        # Check for force flags in both body and footer
        for content in content_to_check:
            for flag, bump_type in [
                ("[force-major]", VersionBumpType.MAJOR),
                ("[force-minor]", VersionBumpType.MINOR),
                ("[force-patch]", VersionBumpType.PATCH),
            ]:
                if flag in content:
                    return bump_type

        # Standard conventional commit rules
        if self.breaking:
            return VersionBumpType.MAJOR
        elif self.type == CommitType.FEAT:
            return VersionBumpType.MINOR
        elif self.type == CommitType.FIX:
            return VersionBumpType.PATCH
        # Other commit types (chore, docs, style, etc.) don't trigger version bumps
        return None

    @dataclass(frozen=True)
    class FooterToken:
        """Token parsed from commit footer."""

        key: str
        value: Optional[str] = None

        def __eq__(self, other: object) -> bool:
            if not isinstance(other, ConventionalCommit.FooterToken):
                return NotImplemented
            return self.key == other.key and self.value == other.value

    def get_footer_tokens(self) -> list[FooterToken]:
        """Parse footer section into tokens."""
        tokens = []
        for section in [self.body, self.footer]:
            if section:
                for match in self.FOOTER_TOKEN_PATTERN.finditer(section):
                    key = match.group("key")
                    value = match.group("value")
                    if value:  # If key=value format
                        tokens.append(self.FooterToken(key, value))
                    else:  # If standalone token
                        tokens.append(self.FooterToken(key))
        return tokens

    def get_prerelease_label(self) -> Optional[str]:
        """Extract pre-release label from commit footer."""
        for token in self.get_footer_tokens():
            if token.key == "pre-release" and token.value in ["alpha", "beta", "rc"]:
                return token.value
        return None


class Version:
    """Semantic version wrapper around packaging.version.Version.

    Provides a high-level interface for version manipulation while using
    the packaging library's robust version parsing underneath.

    Example:
        ```python
        version = Version.parse("1.2.3-beta+build.123")
        str(version)  # "1.2.3-beta+build.123"
        ```
    """

    def __init__(self, version_string: str):
        """Initialize Version with a version string.

        Args:
            version_string: String in semver format (X.Y.Z[-pre][+build])

        Raises:
            InvalidVersion: If version string is not valid semver
        """
        self._version = PackagingVersion(version_string)

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
            # Map PEP 440 pre-release types to SemVer format
            pre_type = {"a": "alpha", "b": "beta", "rc": "rc"}.get(
                self._version.pre[0], self._version.pre[0]
            )
            return pre_type
        return None

    @property
    def build(self) -> Optional[str]:
        """Build metadata if any."""
        return self._version.local if self._version.local else None

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
        """Convert to string representation in SemVer format."""
        version = f"{self.major}.{self.minor}.{self.patch}"

        if self._version.pre:
            # Convert PEP 440 pre-release to SemVer format
            pre_type = {"a": "alpha", "b": "beta", "rc": "rc"}.get(self._version.pre[0])
            if pre_type:
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

        return Version(version_str)


def parse_version(version_str: str) -> Version:
    """Parse a version string into a Version object."""
    return Version.parse(version_str)


def bump_version(current: str, bump_type: VersionBumpType) -> str:
    """Bump the version according to semver rules."""
    version = Version.parse(current)
    return str(version.bump(bump_type))
