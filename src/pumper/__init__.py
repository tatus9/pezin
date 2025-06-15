"""Automated version bumping and changelog management.

Example:
    ```bash
    # Install pre-commit hook
    pre-commit install --hook-type commit-msg

    # Run manually
    pumper bump minor
    ```
"""

from .core.version import Version, VersionBumpType
from .core.commit import ConventionalCommit, CommitType, BumpType
from .core.changelog import ChangelogConfig, ChangelogManager

__version__ = "0.1.0"

__all__ = [
    "Version",
    "VersionBumpType",
    "ConventionalCommit",
    "CommitType",
    "BumpType",
    "ChangelogConfig",
    "ChangelogManager",
]
