import pytest
from pumper.core.version import Version, VersionBumpType
from packaging.version import InvalidVersion


def test_version_parsing_basic():
    """Test basic version string parsing."""
    version = Version.parse("1.2.3")
    assert str(version) == "1.2.3"
    assert version.major == 1
    assert version.minor == 2
    assert version.patch == 3
    assert version.prerelease is None
    assert version.build is None


def test_version_parsing_prerelease():
    """Test parsing versions with pre-release labels."""
    version = Version.parse("1.2.3-beta")
    assert str(version) == "1.2.3-beta"
    assert version.prerelease == "beta"


def test_version_parsing_build():
    """Test parsing versions with build metadata."""
    version = Version.parse("1.2.3+build.123")
    assert str(version) == "1.2.3+build.123"
    assert version.build == "build.123"


def test_version_parsing_full():
    """Test parsing versions with both pre-release and build metadata."""
    version = Version.parse("1.2.3-alpha+build.123")
    assert str(version) == "1.2.3-alpha+build.123"
    assert version.prerelease == "alpha"
    assert version.build == "build.123"


def test_invalid_version():
    """Test handling of invalid version strings."""
    with pytest.raises(InvalidVersion):
        Version.parse("not.a.version")


def test_version_bump_major():
    """Test major version bumping."""
    version = Version.parse("1.2.3")
    new_version = version.bump(VersionBumpType.MAJOR)
    assert str(new_version) == "2.0.0"


def test_version_bump_minor():
    """Test minor version bumping."""
    version = Version.parse("1.2.3")
    new_version = version.bump(VersionBumpType.MINOR)
    assert str(new_version) == "1.3.0"


def test_version_bump_patch():
    """Test patch version bumping."""
    version = Version.parse("1.2.3")
    new_version = version.bump(VersionBumpType.PATCH)
    assert str(new_version) == "1.2.4"


def test_version_bump_with_prerelease():
    """Test version bumping with pre-release label."""
    version = Version.parse("1.2.3")
    new_version = version.bump(VersionBumpType.MINOR, prerelease="alpha")
    assert str(new_version) == "1.3.0-alpha"


def test_version_bump_maintains_build():
    """Test that version bumping maintains build metadata."""
    version = Version.parse("1.2.3+build.123")
    new_version = version.bump(VersionBumpType.MINOR)
    assert str(new_version) == "1.3.0+build.123"
