from datetime import datetime

import pytest

from pumper.core.changelog import (
    DEFAULT_SECTIONS,
    ChangelogConfig,
    ChangelogManager,
    CommitType,
    ConventionalCommit,
)


@pytest.fixture
def sample_commits():
    """Fixture providing sample conventional commits."""
    return [
        ConventionalCommit.parse("feat(api): add new endpoint"),
        ConventionalCommit.parse("fix(core): fix critical bug"),
        ConventionalCommit.parse("docs: update readme"),
        ConventionalCommit.parse(
            "feat!: breaking change\n\nBREAKING CHANGE: API update"
        ),
    ]


@pytest.fixture
def temp_changelog(tmp_path):
    """Fixture providing a temporary changelog file."""
    path = tmp_path / "CHANGELOG.md"
    path.write_text("# Changelog\n\n## [Unreleased]\n")
    return path


def test_changelog_config_defaults():
    """Test default changelog configuration."""
    config = ChangelogConfig()
    assert config.sections == DEFAULT_SECTIONS
    assert config.skip_types == []
    assert config.unreleased_label == "Unreleased"
    assert "Keep a Changelog" in config.header_template


def test_changelog_config_custom():
    """Test custom changelog configuration."""
    custom_sections = {
        "breaking": "Breaking Changes",
        CommitType.FEAT: "New Features",
    }
    config = ChangelogConfig(
        sections=custom_sections,
        skip_types=["chore", "test"],
        repo_url="https://github.com/user/repo",
        unreleased_label="Coming Soon",
    )

    assert config.sections == custom_sections
    assert config.skip_types == ["chore", "test"]
    assert config.repo_url == "https://github.com/user/repo"
    assert config.unreleased_label == "Coming Soon"


def test_parse_empty_changelog():
    """Test parsing an empty changelog."""
    manager = ChangelogManager()
    sections = manager.parse_changelog("")
    assert sections == {}


def test_parse_changelog_with_versions():
    """Test parsing changelog with multiple versions."""
    content = """# Changelog

## [2.0.0] - 2023-01-01
### ✨ Features
- New feature 1

## [1.0.0] - 2022-12-31
### 🐛 Bug Fixes
- Fix bug 1
"""
    manager = ChangelogManager()
    sections = manager.parse_changelog(content)

    assert "2.0.0" in sections
    assert "1.0.0" in sections
    header_lines = [line for line in sections["2.0.0"] if line.startswith("### ")]
    assert any("✨ Features" in line for line in header_lines)
    header_lines = [line for line in sections["1.0.0"] if line.startswith("### ")]
    assert any("🐛 Bug Fixes" in line for line in header_lines)


def test_format_commit_basic():
    """Test basic commit formatting."""
    manager = ChangelogManager()
    commit = ConventionalCommit.parse("feat: new feature")
    entry = manager.format_commit(commit)
    assert entry == "- new feature"


def test_format_commit_with_scope():
    """Test formatting commit with scope."""
    manager = ChangelogManager()
    commit = ConventionalCommit.parse("fix(core): major fix")
    entry = manager.format_commit(commit)
    assert entry == "- **core:** major fix"


def test_format_commit_breaking():
    """Test formatting breaking change commit."""
    manager = ChangelogManager()
    commit = ConventionalCommit.parse("feat!: breaking change")
    entry = manager.format_commit(commit)
    assert entry == "- 💥 breaking change"


def test_format_commit_skip_type():
    """Test skipping configured commit types."""
    config = ChangelogConfig(skip_types=["chore"])
    manager = ChangelogManager(config)
    commit = ConventionalCommit.parse("chore: update deps")
    entry = manager.format_commit(commit)
    assert entry is None


def test_group_commits(sample_commits):
    """Test grouping commits by type."""
    manager = ChangelogManager()
    sections = manager.group_commits(sample_commits)

    assert "breaking" in sections
    assert "feat" in sections
    assert "fix" in sections
    assert "docs" in sections


def test_generate_version_links():
    """Test generating version comparison links."""
    config = ChangelogConfig(repo_url="https://github.com/user/repo")
    manager = ChangelogManager(config)

    links = manager.generate_version_links("2.0.0", {"1.0.0": [], "Unreleased": []})

    assert any("compare/v1.0.0...v2.0.0" in link for link in links)
    assert any("compare/v2.0.0...HEAD" in link for link in links)
    assert any("[Unreleased]" in link for link in links)


def test_update_changelog_new_version(temp_changelog, sample_commits):
    """Test updating changelog with a new version."""
    config = ChangelogConfig(repo_url="https://github.com/user/repo")
    manager = ChangelogManager(config)

    date = datetime(2023, 1, 1)
    manager.update_changelog(temp_changelog, "1.0.0", sample_commits, date)

    content = temp_changelog.read_text()
    assert "## [1.0.0] - 2023-01-01" in content
    assert "### ✨ Features" in content
    assert "### 🐛 Bug Fixes" in content
    assert "### ⚠ BREAKING CHANGES" in content
    assert "[1.0.0]:" in content


def test_update_changelog_multiple_versions(temp_changelog, sample_commits):
    """Test updating changelog with multiple versions."""
    config = ChangelogConfig()
    manager = ChangelogManager(config)

    # Add first version
    manager.update_changelog(temp_changelog, "1.0.0", sample_commits)

    # Add second version
    new_commits = [ConventionalCommit.parse("feat: another feature")]
    manager.update_changelog(temp_changelog, "1.1.0", new_commits)

    content = temp_changelog.read_text()
    assert "## [1.1.0]" in content
    assert "## [1.0.0]" in content
    assert "another feature" in content


def test_update_changelog_with_custom_config(temp_changelog, sample_commits):
    """Test changelog update with custom configuration."""
    config = ChangelogConfig(
        sections={
            "breaking": "⚠ BREAKING CHANGES",
            CommitType.FEAT: "✨ Features",
        },
        skip_types=["docs"],
        unreleased_label="Coming Soon",
    )
    manager = ChangelogManager(config)

    manager.update_changelog(temp_changelog, "1.0.0", sample_commits)

    content = temp_changelog.read_text()
    assert "### ✨ Features" in content
    assert "update readme" not in content
    # By default, Unreleased section should still be there
    assert "## [Unreleased]" in content
