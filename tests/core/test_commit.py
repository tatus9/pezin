import pytest

from pezin.core.commit import BumpType, CommitType, ConventionalCommit, FooterToken


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


def test_fixup_commit_detection():
    """Test detecting fixup and squash commits."""
    test_cases = [
        ("fixup! feat: add new feature", True),
        ("squash! fix: bug fix", True),
        ("FIXUP! chore: update deps", True),
        ("SQUASH! docs: update readme", True),
        ("fixup!feat: missing space", True),
        ("squash!fix: missing space", True),
        ("feat: fixup in description", False),
        ("fix: squash this", False),
        ("chore: normal commit", False),
        ("", False),
        ("just text", False),
        ("fixup prefix without exclamation", False),
        ("squash prefix without exclamation", False),
    ]

    for message, expected_result in test_cases:
        assert ConventionalCommit.is_fixup_commit(message) == expected_result


def test_parse_with_fixup_handling():
    """Test parsing commits with fixup handling."""
    # Regular commit should parse normally
    regular_commit = "feat: add new feature"
    parsed = ConventionalCommit.parse_with_fixup_handling(regular_commit)
    assert parsed is not None
    assert parsed.type == CommitType.FEAT
    assert parsed.description == "add new feature"

    # Fixup commit should return None
    fixup_commit = "fixup! feat: add new feature"
    parsed = ConventionalCommit.parse_with_fixup_handling(fixup_commit)
    assert parsed is None

    # Squash commit should return None
    squash_commit = "squash! fix: bug fix"
    parsed = ConventionalCommit.parse_with_fixup_handling(squash_commit)
    assert parsed is None

    # Invalid conventional commit (non-fixup) should raise ValueError
    with pytest.raises(ValueError):
        ConventionalCommit.parse_with_fixup_handling("invalid commit message")


def test_fixup_commit_edge_cases():
    """Test edge cases for fixup commit detection."""
    test_cases = [
        # Edge cases that should be detected as fixup
        ("fixup! ", True),  # Empty fixup
        ("squash! ", True),  # Empty squash
        ("fixup!\tfeat: tab after exclamation", True),  # Tab whitespace
        ("squash!\nfix: newline after exclamation", True),  # Newline whitespace
        ("FIXUP! FEAT: ALL CAPS", True),  # All caps
        ("Fixup! Mixed: case", True),  # Mixed case
        ("squASH! weird: CaSe", True),  # Weird case
        # Edge cases that should NOT be detected as fixup
        ("fixup", False),  # Missing exclamation
        ("squash", False),  # Missing exclamation
        ("prefix fixup!", False),  # Not at start
        ("some fixup! text", False),  # In middle
        ("text squash! more", False),  # In middle
        ("!fixup feat: backwards", False),  # Wrong order
        ("fix up! spaces", False),  # Spaces in keyword
        ("squ ash! spaces", False),  # Spaces in keyword
    ]

    for message, expected_result in test_cases:
        assert ConventionalCommit.is_fixup_commit(message) == expected_result, (
            f"Failed for: '{message}'"
        )


def test_fixup_with_multiline_messages():
    """Test fixup detection with multiline commit messages."""
    multiline_fixup = """fixup! feat: add authentication

This is a fixup commit that includes
multiple lines of description.

It should still be detected as a fixup commit."""

    assert ConventionalCommit.is_fixup_commit(multiline_fixup)
    assert ConventionalCommit.parse_with_fixup_handling(multiline_fixup) is None

    multiline_squash = """squash! fix(auth): fix login bug

This squash commit also has
multiple lines and should be
properly detected."""

    assert ConventionalCommit.is_fixup_commit(multiline_squash)
    assert ConventionalCommit.parse_with_fixup_handling(multiline_squash) is None
