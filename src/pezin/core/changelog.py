"""Changelog management utilities.

This module provides tools for managing CHANGELOG.md files following the
Keep a Changelog format (https://keepachangelog.com/) and conventional commits.

Example:
    ```python
    config = ChangelogConfig(repo_url="https://github.com/user/repo")
    manager = ChangelogManager(config)

    # Update changelog with new version
    manager.update_changelog(
        path=Path("CHANGELOG.md"),
        version="1.2.3",
        commits=[commit1, commit2],
        date=datetime.now()
    )
    ```
"""

import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from .commit import CommitType, ConventionalCommit

# Default section headers for different commit types
DEFAULT_SECTIONS = {
    "breaking": "⚠ BREAKING CHANGES",
    CommitType.FEAT: "✨ Features",
    CommitType.FIX: "🐛 Bug Fixes",
    CommitType.DOCS: "📚 Documentation",
    CommitType.STYLE: "💎 Style",
    CommitType.REFACTOR: "♻️ Refactor",
    CommitType.PERF: "⚡ Performance",
    CommitType.TEST: "🧪 Tests",
    CommitType.CHORE: "🔧 Chore",
}


@dataclass
class ChangelogConfig:
    """Configuration for changelog generation.

    Controls how the changelog is formatted and what content is included.

    Args:
        sections: Custom section headers for commit types
        skip_types: Commit types to exclude from changelog
        repo_url: Repository URL for version comparison links
        unreleased_label: Label for unreleased changes section
        header_template: Custom header template for changelog
    """

    sections: Optional[Dict[str, str]] = None
    skip_types: Optional[List[str]] = None
    repo_url: Optional[str] = None
    unreleased_label: str = "Unreleased"
    header_template: Optional[str] = None

    def __post_init__(self):
        """Initialize with defaults if not provided."""
        self.sections = self.sections or DEFAULT_SECTIONS.copy()
        self.skip_types = self.skip_types or []
        self.header_template = self.header_template or self.DEFAULT_HEADER

    DEFAULT_HEADER = """# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).
"""


class ChangelogManager:
    """Manages changelog generation and updates.

    Handles:
    - Parsing existing changelog content
    - Generating new version sections
    - Formatting commit messages
    - Managing version comparison links
    """

    VERSION_HEADER_PATTERN = re.compile(r"^## \[([^\]]+)\]( - (\d{4}-\d{2}-\d{2}))?")

    def __init__(self, config: Optional[ChangelogConfig] = None):
        """Initialize with optional configuration.

        Args:
            config: Configuration for changelog management
        """
        self.config = config or ChangelogConfig()

    def parse_changelog(self, content: str) -> Dict[str, List[str]]:
        """Parse changelog content into version sections.

        Args:
            content: Raw changelog content

        Returns:
            Dict mapping version numbers to their content lines
        """
        sections: Dict[str, List[str]] = {}
        current_version = None
        current_section = None
        current_lines = []
        section_content = []

        for line in content.split("\n"):
            if match := self.VERSION_HEADER_PATTERN.match(line):
                # Store previous version's content
                if current_version:
                    sections[current_version] = current_lines + section_content
                # Start new version
                current_version = match.group(1)
                current_lines = [line]
                section_content = []
            elif line.startswith("### "):
                # Store previous section content
                if current_section:
                    current_lines.extend(section_content)
                # Start new section
                current_section = line[4:].strip()
                section_content = [line]
            elif current_version:
                if current_section:
                    section_content.append(line)
                else:
                    current_lines.append(line)

        # Store final section
        if current_version:
            if current_section:
                current_lines.extend(section_content)
            sections[current_version] = current_lines

        return sections

    def format_commit(self, commit: ConventionalCommit) -> Optional[str]:
        """Format a commit for the changelog.

        Args:
            commit: Conventional commit to format

        Returns:
            str: Formatted changelog entry
            None: If commit should be skipped
        """
        if commit.type.value in self.config.skip_types:
            return None

        entry = commit.description
        if commit.scope:
            entry = f"**{commit.scope}:** {entry}"

        if commit.breaking:
            entry = f"💥 {entry}"

        return f"- {entry}"

    def group_commits(self, commits: List[ConventionalCommit]) -> Dict[str, List[str]]:
        """Group formatted commit messages by section.

        Args:
            commits: List of commits to group

        Returns:
            Dict mapping section names to lists of formatted commits
        """
        sections: Dict[str, List[str]] = {}

        for commit in commits:
            section = "breaking" if commit.breaking else commit.type.value
            if section not in sections:
                sections[section] = []

            if entry := self.format_commit(commit):
                sections[section].append(entry)

        return sections

    def generate_version_links(
        self, version: str, sections: Dict[str, List[str]]
    ) -> List[str]:
        """Generate version comparison links.

        Args:
            version: New version being added
            sections: Existing changelog sections

        Returns:
            List of formatted version comparison links
        """
        if not self.config.repo_url:
            return []

        versions = list(sections.keys())

        # Filter out unreleased section and sort versions
        versions = [v for v in versions if v != self.config.unreleased_label]
        versions.insert(0, version)  # Add new version at the start

        links = [
            f"[{self.config.unreleased_label}]: {self.config.repo_url}/compare/v{version}...HEAD"
        ]
        # Generate version comparison links
        for i, ver in enumerate(versions):
            if i == len(versions) - 1:
                # Last version just gets a release link
                links.append(f"[{ver}]: {self.config.repo_url}/releases/tag/v{ver}")
            else:
                # Other versions get comparison links
                next_ver = versions[i + 1]
                links.append(
                    f"[{ver}]: {self.config.repo_url}/compare/v{next_ver}...v{ver}"
                )

        return links

    def update_changelog(
        self,
        path: Path,
        version: str,
        commits: List[ConventionalCommit],
        date: Optional[datetime] = None,
    ) -> None:
        """Update changelog for a new version.

        Args:
            path: Path to changelog file
            version: New version being released
            commits: Commits since last release
            date: Release date (defaults to today)
        """
        date = date or datetime.now()
        date_str = date.strftime("%Y-%m-%d")

        # Create file if it doesn't exist
        if not path.exists():
            path.write_text(
                f"{self.config.header_template}\n\n## [{self.config.unreleased_label}]\n"
            )

        # Parse existing content
        content = path.read_text()
        sections = self.parse_changelog(content)

        # Group commits by type
        changes = self.group_commits(commits)

        # Format new version section
        new_section = [f"## [{version}] - {date_str}"]

        for section_type, section_title in self.config.sections.items():
            if section_type in changes and changes[section_type]:
                new_section.extend([f"### {section_title}", ""])
                new_section.extend(changes[section_type])
                new_section.append("")

        if links := self.generate_version_links(version, sections):
            new_section.extend(["", *links])

        # Write updated content
        new_content = "\n".join(
            [
                self.config.header_template,
                "",
                *new_section,
                "",
                *(line for ver in sections for line in sections[ver]),
            ]
        )

        path.write_text(new_content)


def format_commit_message(
    commit: ConventionalCommit, include_scope: bool = True
) -> str:
    """Format a commit message for the changelog.

    Helper function to format a single commit message consistently.

    Args:
        commit: Conventional commit to format
        include_scope: Whether to include scope in output

    Returns:
        str: Formatted commit message
    """
    message = commit.description
    if include_scope and commit.scope:
        message = f"**{commit.scope}:** {message}"
    if commit.breaking:
        message = f"💥 {message}"
    return f"- {message}"
