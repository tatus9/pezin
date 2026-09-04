from datetime import datetime

import pytest

from pezin.core.changelog import (
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


def test_update_changelog_idempotent_on_duplicate_version(
    temp_changelog, sample_commits
):
    """Re-running update_changelog with the same version is a no-op for that section."""
    manager = ChangelogManager(ChangelogConfig())

    manager.update_changelog(temp_changelog, "1.2.3", sample_commits)
    first_content = temp_changelog.read_text()
    assert first_content.count("## [1.2.3]") == 1

    # Second run with the same version must not duplicate the section.
    new_commits = [ConventionalCommit.parse("feat: ignored on rerun")]
    manager.update_changelog(temp_changelog, "1.2.3", new_commits)
    second_content = temp_changelog.read_text()

    assert second_content == first_content
    assert second_content.count("## [1.2.3]") == 1
    assert "ignored on rerun" not in second_content


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


def test_update_changelog_keeps_unreleased_at_top(temp_changelog, sample_commits):
    """Keep-a-Changelog ordering: [Unreleased] stays directly below the header
    and the new version section is inserted below it, not above everything."""
    manager = ChangelogManager()
    manager.update_changelog(temp_changelog, "1.1.0", sample_commits)

    content = temp_changelog.read_text()
    header_idx = content.index("# Changelog")
    unreleased_idx = content.index("## [Unreleased]")
    version_idx = content.index("## [1.1.0]")

    assert header_idx < unreleased_idx < version_idx


def test_update_changelog_promotes_unreleased_entries(tmp_path, sample_commits):
    """Entries accumulated under [Unreleased] are promoted into the new
    version section and an empty [Unreleased] is re-created at the top."""
    path = tmp_path / "CHANGELOG.md"
    path.write_text(
        "# Changelog\n\n"
        "## [Unreleased]\n"
        "### ✨ Features\n\n"
        "- support plugins\n\n"
        "## [0.7.0] - 2026-05-01\n"
        "### ✨ Features\n\n"
        "- initial release\n"
    )

    manager = ChangelogManager()
    manager.update_changelog(
        path, "0.8.0", [ConventionalCommit.parse("feat: add exporter")]
    )

    content = path.read_text()
    unreleased_idx = content.index("## [Unreleased]")
    v080 = content.index("## [0.8.0]")
    v070 = content.index("## [0.7.0]")

    # Order: header, Unreleased, 0.8.0, 0.7.0
    assert unreleased_idx < v080 < v070

    # Unreleased is empty again
    unreleased_block = content[unreleased_idx:v080]
    assert "- " not in unreleased_block

    # Promoted and new entries share the 0.8.0 section
    section_080 = content[v080:v070]
    assert "- add exporter" in section_080
    assert "- support plugins" in section_080
    # Only one Features heading in the merged section
    assert section_080.count("### ✨ Features") == 1
    # The older section is untouched
    assert "- initial release" in content[v070:]


def test_update_changelog_dedupes_promoted_duplicates(tmp_path):
    """A pre-recorded Unreleased entry identical to the commit's own entry
    must not appear twice in the promoted section."""
    path = tmp_path / "CHANGELOG.md"
    path.write_text(
        "# Changelog\n\n## [Unreleased]\n### ✨ Features\n\n- add exporter\n"
    )

    manager = ChangelogManager()
    manager.update_changelog(
        path, "0.8.0", [ConventionalCommit.parse("feat: add exporter")]
    )

    assert path.read_text().count("- add exporter") == 1


def test_update_changelog_preserves_existing_header(tmp_path, sample_commits):
    """A customized header is preserved verbatim; the template is only used
    when creating the file."""
    custom_header = "# My project changelog\n\nCustom intro paragraph."
    path = tmp_path / "CHANGELOG.md"
    path.write_text(f"{custom_header}\n\n## [Unreleased]\n")

    manager = ChangelogManager()
    manager.update_changelog(path, "1.0.0", sample_commits)

    content = path.read_text()
    assert content.startswith(custom_header + "\n")
    assert "Keep a Changelog" not in content.split("## [Unreleased]")[0]


def test_update_changelog_second_bump_keeps_order(temp_changelog, sample_commits):
    """Successive bumps keep versions newest-first below [Unreleased]."""
    manager = ChangelogManager()
    manager.update_changelog(temp_changelog, "1.1.0", sample_commits)
    manager.update_changelog(
        temp_changelog, "1.2.0", [ConventionalCommit.parse("feat: second feature")]
    )

    content = temp_changelog.read_text()
    order = [
        content.index("## [Unreleased]"),
        content.index("## [1.2.0]"),
        content.index("## [1.1.0]"),
    ]
    assert order == sorted(order)


def test_update_changelog_promotes_multiline_entries(tmp_path):
    """Multi-line bullets keep their continuation lines when promoted."""
    path = tmp_path / "CHANGELOG.md"
    path.write_text(
        "# Changelog\n\n"
        "## [Unreleased]\n"
        "### 🐛 Bug Fixes\n\n"
        "- `pezin install-hooks` no longer generates hooks with a\n"
        "  `#!/usr/bin/env python3` shebang. Hooks are pinned\n"
        "  to the installing interpreter.\n\n"
        "### ✨ Features\n\n"
        "- `python -m pezin` now works\n"
    )

    manager = ChangelogManager()
    manager.update_changelog(
        path, "0.9.0", [ConventionalCommit.parse("feat: add exporter")]
    )

    content = path.read_text()
    section = content[content.index("## [0.9.0]") :]
    assert (
        "- `pezin install-hooks` no longer generates hooks with a\n"
        "  `#!/usr/bin/env python3` shebang. Hooks are pinned\n"
        "  to the installing interpreter." in section
    )
    assert "`python -m pezin` now works" in section
    assert "- add exporter" in section


def test_update_changelog_consolidates_link_definitions(tmp_path):
    """Link definitions are emitted once at the bottom, never duplicated."""
    manager = ChangelogManager(
        ChangelogConfig(repo_url="https://github.com/tatus9/pezin")
    )
    path = tmp_path / "CHANGELOG.md"
    path.write_text(
        "# Changelog\n\n"
        "## [Unreleased]\n\n"
        "## [0.8.2] - 2026-08-23\n\n"
        "- old fix\n\n"
        "[Unreleased]: https://github.com/tatus9/pezin/compare/v0.8.2...HEAD\n"
        "[0.8.2]: https://github.com/tatus9/pezin/compare/v0.8.1...v0.8.2\n"
    )

    manager.update_changelog(
        path, "0.9.0", [ConventionalCommit.parse("feat: add exporter")]
    )

    content = path.read_text()
    assert content.count("[0.8.2]:") == 1
    assert content.count("[Unreleased]:") == 1
    assert content.count("[0.9.0]:") == 1
    # Link block is at the very bottom, after all sections; the oldest
    # version gets a release-tag link.
    assert content.rstrip().endswith(
        "[0.8.2]: https://github.com/tatus9/pezin/releases/tag/v0.8.2"
    )
    # No stale link lines remain inside version sections
    assert "[Unreleased]:" not in content.split("## [0.9.0]")[0]
