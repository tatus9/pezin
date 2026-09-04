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

from ..logging import get_logger
from .commit import CommitType, ConventionalCommit

logger = get_logger()

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

    def create_if_missing(self, path: Path) -> bool:
        """Create a Keep-a-Changelog-formatted file if `path` is absent.

        Returns True if the file was created, False if it already existed.
        Parent directories are created as needed. Used by both the CLI and
        the post-commit hook so the "first-run on a virgin repo" path is
        shared.
        """
        if path.exists():
            return False
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            f"{self.config.header_template}\n\n## [{self.config.unreleased_label}]\n"
        )
        return True

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
        unreleased_label = self.config.unreleased_label

        # Read existing content; create with the template header when missing.
        if path.exists():
            content = path.read_text()
        else:
            content = f"{self.config.header_template}\n\n## [{unreleased_label}]\n"

        # Preserve the user's header verbatim: everything above the first
        # version heading. The configured template is only used when the
        # file is created above.
        header = self.extract_header(content)
        sections = self.parse_changelog(content)

        # Idempotency guard: if a section for this version already exists,
        # do not append a duplicate. The caller may re-trigger us on the
        # same commit (manual re-amend, partial-failure retries, etc.).
        if version in sections:
            logger.debug(f"CHANGELOG.md already has a [{version}] section; skipping")
            return

        # Group commits by type
        changes = self.group_commits(commits)

        # Promote entries accumulated under [Unreleased] into the new
        # version section, deduplicated against this commit's own entries.
        promoted = self.split_unreleased_entries(sections.get(unreleased_label, []))
        merged: Dict[str, List[str]] = {}
        for section_type, section_title in self.config.sections.items():
            section_lines = changes.get(section_type) or []
            if section_lines:
                merged[section_title] = list(section_lines)
        for title, entry_lines in promoted.items():
            target = merged.setdefault(title, [])
            for line in entry_lines:
                if line not in target:
                    target.append(line)

        # Format new version section: configured titles first, then any
        # promoted subsection titles the config does not know about.
        new_section = [f"## [{version}] - {date_str}"]
        emitted_titles: set = set()
        for section_title in self.config.sections.values():
            if merged.get(section_title):
                new_section.extend([f"### {section_title}", ""])
                new_section.extend(
                    line
                    for entry in merged[section_title]
                    for line in entry.split("\n")
                )
                new_section.append("")
                emitted_titles.add(section_title)
        for title in promoted:
            if title not in emitted_titles and merged.get(title):
                new_section.extend([f"### {title}", ""])
                new_section.extend(
                    line for entry in merged[title] for line in entry.split("\n")
                )
                new_section.append("")

        links = self.generate_version_links(version, sections)

        # Keep-a-Changelog ordering: header, empty [Unreleased], the new
        # version section, then older sections (already newest-first).
        # Existing link-definition lines are stripped everywhere and
        # re-emitted once at the bottom, so regenerated links never
        # duplicate (or shadow) older definitions.
        link_pattern = re.compile(r"^\[[^\]]+\]:\s*\S+")
        older = [ver for ver in sections if ver != unreleased_label]
        new_content = "\n".join(
            [
                header,
                "",
                f"## [{unreleased_label}]",
                "",
                *new_section,
                "",
                *(
                    line
                    for ver in older
                    for line in sections[ver]
                    if not link_pattern.match(line)
                ),
            ]
        )
        if links:
            new_content = new_content.rstrip("\n") + "\n\n" + "\n".join(links)
        if not new_content.endswith("\n"):
            new_content += "\n"

        path.write_text(new_content)

    def extract_header(self, content: str) -> str:
        """Return the changelog header: content above the first version heading.

        Args:
            content: Raw changelog content

        Returns:
            Header text without trailing blank lines. If no version heading
            exists, the whole content is treated as header.
        """
        lines = content.split("\n")
        for idx, line in enumerate(lines):
            if self.VERSION_HEADER_PATTERN.match(line):
                return "\n".join(lines[:idx]).rstrip("\n")
        return content.rstrip("\n")

    def split_unreleased_entries(
        self, section_lines: List[str]
    ) -> Dict[str, List[str]]:
        """Split an ``[Unreleased]`` section body into subsection entries.

        Args:
            section_lines: Parsed lines of the unreleased section (the first
                line is the ``## [Unreleased]`` heading itself)

        Returns:
            Dict mapping subsection title (from ``###`` headings, empty
            string for entries directly under the version heading) to the
            formatted entries. Entries may span multiple lines (indented
            continuation lines stay attached to their bullet).
        """
        result: Dict[str, List[str]] = {}
        current_title = ""
        entries: List[str] = []

        def _flush() -> None:
            if entries:
                result.setdefault(current_title, []).extend(entries)

        for line in section_lines[1:]:
            if line.startswith("### "):
                _flush()
                entries = []
                current_title = line[4:].strip()
            elif line.startswith("- "):
                _flush()
                entries = [line]
            elif line.strip() and entries:
                # Continuation line of the current multi-line bullet.
                entries.append(line)
        _flush()
        return result


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
