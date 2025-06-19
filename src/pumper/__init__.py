"""Automated version bumping and changelog management.

Example:
    ```bash
    # Install pre-commit hook
    pre-commit install --hook-type commit-msg

    # Run manually
    pumper bump minor
    ```
"""

from .core.changelog import ChangelogConfig, ChangelogManager
from .core.commit import BumpType, CommitType, ConventionalCommit
from .core.version import Version, VersionBumpType

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
