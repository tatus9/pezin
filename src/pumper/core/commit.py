"""Conventional Commit message parsing."""

import re
from dataclasses import dataclass
from enum import Enum
from typing import Optional, List


class BumpType(str, Enum):
    """Type of version bump to perform."""

    MAJOR = "major"
    MINOR = "minor"
    PATCH = "patch"
    NONE = "none"


class CommitType(str, Enum):
    """Type of commit change."""

    FIX = "fix"
    FEAT = "feat"
    CHORE = "chore"
    DOCS = "docs"
    STYLE = "style"
    REFACTOR = "refactor"
    PERF = "perf"
    TEST = "test"
    BUILD = "build"
    CI = "ci"

    @classmethod
    def from_str(cls, value: str) -> "CommitType":
        """Create from string value."""
        try:
            return cls(value.lower())
        except ValueError:
            raise ValueError(f"Invalid commit type: {value}")


@dataclass
class FooterToken:
    """Token parsed from commit footer."""

    key: str
    value: Optional[str] = None

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, FooterToken):
            return NotImplemented
        return self.key == other.key and self.value == other.value


@dataclass
class ConventionalCommit:
    """Parsed conventional commit message."""

    type: CommitType
    scope: Optional[str]
    breaking: bool
    description: str
    body: Optional[str]
    footer: Optional[str]

    # Regular expressions for parsing
    HEADER_PATTERN = re.compile(
        r"^(?P<type>[a-z]+)"
        r"(?:\((?P<scope>[^\)]+)\))?"
        r"(?P<breaking>!)?:"
        r"\s*(?P<description>.+)$"
    )
    FOOTER_PATTERN = re.compile(r"\[(?P<key>[^\]=]+)(?:=(?P<value>[^\]]+))?\]")

    @classmethod
    def parse(cls, message: str) -> "ConventionalCommit":
        """Parse a conventional commit message.

        Args:
            message: Full commit message to parse

        Returns:
            Parsed ConventionalCommit instance

        Raises:
            ValueError: If message doesn't match conventional format
        """
        # Split into parts
        parts = message.strip().split("\n\n", maxsplit=2)
        header = parts[0]
        body = parts[1] if len(parts) > 1 else None
        footer = parts[2] if len(parts) > 2 else None

        # For the header, only use the first line (in case of squashed commits)
        # This handles cases where squashed commits have multiple commit messages
        header_lines = header.split("\n")
        first_line = header_lines[0].strip()

        # Parse header (first line only)
        if match := cls.HEADER_PATTERN.match(first_line):
            commit_type = CommitType.from_str(match.group("type"))
            scope = match.group("scope")
            breaking = bool(match.group("breaking"))
            description = match.group("description")
        else:
            raise ValueError("Invalid commit header format")

        # Move BREAKING CHANGE from body to footer if needed
        if body and "BREAKING CHANGE:" in body:
            if footer:
                footer = f"{body}\n\n{footer}"
            else:
                footer = body
            body = None
            breaking = True
        elif footer and "BREAKING CHANGE:" in footer:
            breaking = True

        return cls(
            type=commit_type,
            scope=scope,
            breaking=breaking,
            description=description,
            body=body,
            footer=footer,
        )

    def get_footer_tokens(self) -> List[FooterToken]:
        """Parse footer section into tokens."""
        tokens = []
        for section in [self.body, self.footer]:
            if section:
                for match in self.FOOTER_PATTERN.finditer(section):
                    key = match.group("key")
                    value = match.group("value")
                    tokens.append(FooterToken(key, value))
        return tokens

    def get_prerelease_label(self) -> Optional[str]:
        """Extract pre-release label from commit footer."""
        for token in self.get_footer_tokens():
            if token.key == "pre-release" and token.value:
                if token.value in ["alpha", "beta", "rc"]:
                    return token.value
        return None

    def get_bump_type(self) -> BumpType:
        """Determine version bump type from commit.

        Returns:
            BumpType enum indicating the type of version bump needed
        """
        # Check for skip flag
        if any(token.key == "skip-bump" for token in self.get_footer_tokens()):
            return BumpType.NONE

        # Check for force flags
        for token in self.get_footer_tokens():
            if token.key == "force-major":
                return BumpType.MAJOR
            if token.key == "force-minor":
                return BumpType.MINOR
            if token.key == "force-patch":
                return BumpType.PATCH

        # Get bump type from commit
        if self.breaking:
            return BumpType.MAJOR
        elif self.type == CommitType.FEAT:
            return BumpType.MINOR
        elif self.type == CommitType.FIX:
            return BumpType.PATCH
        return BumpType.NONE
