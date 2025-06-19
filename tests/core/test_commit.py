import pytest

from pumper.core.commit import BumpType, CommitType, ConventionalCommit, FooterToken


def test_basic_commit_parsing():
    """Test parsing basic commit message."""
    message = "feat: add new feature"
    commit = ConventionalCommit.parse(message)
    assert commit.type == CommitType.FEAT
    assert commit.scope is None
    assert not commit.breaking
    assert commit.description == "add new feature"
    assert commit.body is None
    assert commit.footer is None


def test_commit_with_scope():
    """Test parsing commit with scope."""
    message = "fix(auth): fix login issue"
    commit = ConventionalCommit.parse(message)
    assert commit.type == CommitType.FIX
    assert commit.scope == "auth"
    assert commit.description == "fix login issue"


def test_breaking_change_marker():
    """Test detecting breaking change with ! marker."""
    message = "feat(api)!: redesign endpoint"
    commit = ConventionalCommit.parse(message)
    assert commit.breaking
    assert commit.type == CommitType.FEAT
    assert commit.scope == "api"


def test_breaking_change_footer():
    """Test detecting breaking change in footer."""
    message = """feat(api): redesign endpoint

BREAKING CHANGE: This changes the API structure"""
    commit = ConventionalCommit.parse(message)
    assert commit.breaking
    assert commit.footer == "BREAKING CHANGE: This changes the API structure"


def test_commit_with_body():
    """Test parsing commit with body text."""
    message = """fix(core): handle edge case

This fixes a critical edge case where...
And provides better error handling."""
    commit = ConventionalCommit.parse(message)
    assert (
        commit.body
        == "This fixes a critical edge case where...\nAnd provides better error handling."
    )


def test_invalid_commit_format():
    """Test handling invalid commit message format."""
    with pytest.raises(ValueError):
        ConventionalCommit.parse("not a valid commit message")


def test_footer_token_parsing():
    """Test parsing footer tokens."""
    message = """chore: update deps

[skip-ci]
[pre-release=beta]
[force-major]"""
    commit = ConventionalCommit.parse(message)
    tokens = commit.get_footer_tokens()

    assert len(tokens) == 3
    assert FooterToken("skip-ci") in tokens
    assert FooterToken("pre-release", "beta") in tokens
    assert FooterToken("force-major") in tokens


def test_bump_type_determination():
    """Test determining version bump type."""
    test_cases = [
        ("feat!: breaking", BumpType.MAJOR),
        ("feat: new feature", BumpType.MINOR),
        ("fix: bugfix", BumpType.PATCH),
        ("docs: update readme", BumpType.NONE),
        ("fix: minor fix\n\n[skip-bump]", BumpType.NONE),
        ("chore: update\n\n[force-major]", BumpType.MAJOR),
        ("fix: small fix\n\n[force-minor]", BumpType.MINOR),
        ("feat: new thing\n\n[force-patch]", BumpType.PATCH),
    ]

    for message, expected_type in test_cases:
        commit = ConventionalCommit.parse(message)
        assert commit.get_bump_type() == expected_type


def test_prerelease_label_extraction():
    """Test extracting pre-release labels."""
    test_cases = [
        ("feat: add feature\n\n[pre-release=alpha]", "alpha"),
        ("feat: add feature\n\n[pre-release=beta]", "beta"),
        ("feat: add feature\n\n[pre-release=rc]", "rc"),
        ("feat: add feature\n\n[pre-release=invalid]", None),
        ("feat: add feature", None),
    ]

    for message, expected_label in test_cases:
        commit = ConventionalCommit.parse(message)
        assert commit.get_prerelease_label() == expected_label


def test_multiple_footer_sections():
    """Test parsing commits with multiple footer sections."""
    message = """feat: new feature

This adds an awesome new feature.

Signed-off-by: Dev <dev@example.com>
[skip-ci]
BREAKING CHANGE: Major API update"""

    commit = ConventionalCommit.parse(message)
    assert commit.breaking
    assert commit.body == "This adds an awesome new feature."
    assert "Signed-off-by" in commit.footer
    assert "[skip-ci]" in commit.footer
    assert "BREAKING CHANGE" in commit.footer


def test_scope_special_characters():
    """Test handling scopes with special characters."""
    message = "fix(@core/auth): fix authentication"
    commit = ConventionalCommit.parse(message)
    assert commit.scope == "@core/auth"
    assert commit.description == "fix authentication"


def test_squashed_commit_parsing():
    """Test parsing squashed commits with multiple conventional commit messages."""
    # This simulates a squashed commit where multiple commits were combined
    message = """chore: initial commit

fix: commit amend should not bump version

feat: add loguru as default"""

    commit = ConventionalCommit.parse(message)
    # Should parse only the first line as the header
    assert commit.type == CommitType.CHORE
    assert commit.description == "initial commit"
    assert commit.get_bump_type() == BumpType.NONE

    # The rest should be treated as body and footer due to double newline splits
    assert commit.body == "fix: commit amend should not bump version"
    assert commit.footer == "feat: add loguru as default"
