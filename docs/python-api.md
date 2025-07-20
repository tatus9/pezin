# Python API

## Core Classes

### Version Class

```python
from pezin import Version

# Parse version strings
version = Version.parse("1.2.3")
version = Version.parse("2.0.0-alpha.1")

# Bump versions
new_version = version.bump("major")    # 1.2.3 → 2.0.0
new_version = version.bump("minor")    # 1.2.3 → 1.3.0
new_version = version.bump("patch")    # 1.2.3 → 1.2.4

# Pre-release versions
new_version = version.bump("minor", "alpha")  # 1.2.3 → 1.3.0-alpha.1

# Version comparison
v1 = Version.parse("1.2.3")
v2 = Version.parse("1.3.0")
print(v1 < v2)  # True
```

### ConventionalCommit Class

```python
from pezin import ConventionalCommit

# Parse commit messages
commit = ConventionalCommit.parse("feat(api): add new endpoint")
print(commit.type)        # "feat"
print(commit.scope)       # "api"
print(commit.description) # "add new endpoint"

# Breaking changes
commit = ConventionalCommit.parse("feat!: redesign API")
print(commit.breaking)    # True

commit = ConventionalCommit.parse("""
feat: new auth system

BREAKING CHANGE: The authentication API has been redesigned.
""")
print(commit.breaking)    # True

# Determine version bump
bump_type = commit.get_bump_type()
# Returns: BumpType.MAJOR, BumpType.MINOR, BumpType.PATCH, or BumpType.NONE

# Footer tokens
commit = ConventionalCommit.parse("""
feat: new feature

[skip-bump]
[pre-release=beta]
""")
tokens = commit.get_footer_tokens()
prerelease = commit.get_prerelease_label()  # "beta"
```

### ChangelogManager Class

```python
from pezin import ChangelogManager, ChangelogConfig
from pathlib import Path

# Configure changelog
config = ChangelogConfig(
    repo_url="https://github.com/username/project",
    changelog_file="CHANGELOG.md"
)

# Create manager
manager = ChangelogManager(config)

# Update changelog
commits = [
    ConventionalCommit.parse("feat: add user auth"),
    ConventionalCommit.parse("fix: resolve login bug"),
]

success = manager.update_changelog(
    Path("CHANGELOG.md"),
    "1.1.0",
    commits
)
```

## Utility Functions

### Version Detection

```python
from pezin.core.version import detect_version_file
from pathlib import Path

# Auto-detect version file
version_file = detect_version_file(Path("."))
print(version_file)  # Path to pyproject.toml or package.json

# Read current version
from pezin.utils import read_version
current_version = read_version(version_file)
```

### Git Operations

```python
from pezin.utils import get_commits_since_tag

# Get commits since last tag
commits = get_commits_since_tag()
for commit in commits:
    print(f"{commit.type}: {commit.description}")
```

## Complete Example

```python
from pezin import Version, ConventionalCommit, ChangelogManager, ChangelogConfig
from pathlib import Path
import subprocess

def bump_version():
    # Get current version
    version_file = Path("pyproject.toml")
    current = Version.parse("1.0.0")  # Read from file

    # Get latest commit
    result = subprocess.run(
        ["git", "log", "-1", "--pretty=format:%s%n%b"],
        capture_output=True, text=True
    )

    # Parse commit
    commit = ConventionalCommit.parse(result.stdout)
    bump_type = commit.get_bump_type()

    if bump_type:
        # Bump version
        new_version = current.bump(bump_type)
        print(f"Bumping {current} → {new_version}")

        # Update changelog
        config = ChangelogConfig(repo_url="https://github.com/user/repo")
        manager = ChangelogManager(config)
        manager.update_changelog(Path("CHANGELOG.md"), str(new_version), [commit])

        return new_version

    return None

# Usage
new_version = bump_version()
```

## Error Handling

```python
from pezin import Version, ConventionalCommit
from pezin.exceptions import ParseError

try:
    version = Version.parse("invalid.version")
except ParseError as e:
    print(f"Invalid version: {e}")

try:
    commit = ConventionalCommit.parse("invalid commit message")
except ParseError as e:
    print(f"Invalid commit format: {e}")
```
