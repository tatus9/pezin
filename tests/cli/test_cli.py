"""CLI test suite."""

import logging
import pytest
from pathlib import Path
import tomli
from typer.testing import CliRunner
from pumper.cli.main import app

logging.basicConfig(level=logging.DEBUG)


@pytest.fixture
def cli_runner():
    """Fixture providing a Typer CLI test runner."""
    return CliRunner()


@pytest.fixture
def test_files(tmp_path: Path):
    """Create and copy test files to a directory."""

    def _create_files(path: Path, copy_defaults: bool = True):
        path.mkdir(parents=True, exist_ok=True)
        logging.debug(f"Creating test files in {path}")

        if copy_defaults:
            # Create version file
            version_file = path / "pyproject.toml"
            version_file.write_text('[project]\nversion = "0.1.0"\n')

            # Create changelog file
            changelog_file = path / "CHANGELOG.md"
            changelog_file.write_text("# Changelog\n\n## [Unreleased]\n")

        return path

    return _create_files


def test_cli_help(cli_runner):
    """Test CLI help output."""
    result = cli_runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "Usage:" in result.output
    assert "major" in result.output
    assert "minor" in result.output
    assert "patch" in result.output


# TODO: implement pre-release first
# def test_bump_command_help(cli_runner):
#     """Test bump command help output."""
#     result = cli_runner.invoke(app, ["patch", "--help"])
#     assert result.exit_code == 0
#     assert "--message" in result.output
#     assert "--pre-release" in result.output


def test_bump_command_basic(cli_runner, test_files, tmp_path):
    """Test basic version bump command."""
    with cli_runner.isolated_filesystem() as td:
        test_dir = Path(td)
        version_file = test_dir / "pyproject.toml"
        version_file.write_text('[project]\nversion = "0.1.0"\n')

        changelog_file = test_dir / "CHANGELOG.md"
        changelog_file.write_text("# Changelog\n\n## [Unreleased]\n")

        result = cli_runner.invoke(app, ["patch", "-m", "fix: test fix"])
        assert result.exit_code == 0, f"Command failed:\n{result.output}"

        # Verify version bump
        with open(version_file, "rb") as f:
            config = tomli.load(f)
        assert config["project"]["version"] == "0.1.1"

        # Verify changelog update
        changelog = changelog_file.read_text()
        assert "## [0.1.1]" in changelog
        assert "test fix" in changelog


def test_bump_command_config(cli_runner, test_files, tmp_path):
    """Test bump command with custom configuration."""
    with cli_runner.isolated_filesystem() as td:
        test_dir = Path(td)

        # Create config file with version in it
        config_file = test_dir / "pumper.toml"
        config_file.write_text("""
[project]
version = "0.1.0"

[pumper]
changelog_file = "custom_changelog.md"
""")

        # Create changelog file
        changelog_file = test_dir / "custom_changelog.md"
        changelog_file.write_text("# Changelog\n\n## [Unreleased]\n")

        logging.debug(f"Test directory contents: {list(test_dir.glob('*'))}")
        logging.debug(f"Using config file: {config_file}")

        result = cli_runner.invoke(
            app, ["patch", "--config", str(config_file), "-m", "fix: config test"]
        )
        if result.exit_code != 0:
            logging.error(f"Command output:\n{result.output}")

        assert result.exit_code == 0, f"Command failed:\n{result.output}"

        # Verify changes
        with open(config_file, "rb") as f:
            data = tomli.load(f)
            assert data["project"]["version"] == "0.1.1"

        assert "## [0.1.1]" in changelog_file.read_text()
        assert "config test" in changelog_file.read_text()


def test_bump_command_external_version(cli_runner, test_files, tmp_path):
    """Test bump command with version in external file."""
    with cli_runner.isolated_filesystem() as td:
        test_dir = Path(td)

        # Create external version file
        version_file = test_dir / "VERSION"
        version_file.write_text("0.1.0")

        # Create config file referencing external version
        config_file = test_dir / "pumper.toml"
        config_file.write_text("""
[pumper]
version_file = "VERSION"
changelog_file = "CHANGES.md"
""")

        # Create changelog file
        changelog_file = test_dir / "CHANGES.md"
        changelog_file.write_text("# Changelog\n\n## [Unreleased]\n")

        logging.debug(f"Test directory contents: {list(test_dir.glob('*'))}")
        logging.debug(f"Using config file: {config_file}")

        result = cli_runner.invoke(
            app, ["patch", "--config", str(config_file), "-m", "fix: external version"]
        )
        if result.exit_code != 0:
            logging.error(f"Command output:\n{result.output}")

        assert result.exit_code == 0, f"Command failed:\n{result.output}"

        # Verify changes
        assert version_file.read_text().strip() == "0.1.1"
        assert "## [0.1.1]" in changelog_file.read_text()
        assert "external version" in changelog_file.read_text()


# TODO: implement pre-release first
# def test_bump_command_invalid_prerelease(cli_runner, test_files):
#     """Test bump command with invalid pre-release label."""
#     with cli_runner.isolated_filesystem() as td:
#         test_dir = Path(td)
#         version_file = test_dir / "pyproject.toml"
#         version_file.write_text('[project]\nversion = "0.1.0"\n')

#         result = cli_runner.invoke(app, [
#             "patch",
#             "--pre-release", "invalid",
#             "-m", "fix: test"
#         ])
#         assert result.exit_code == 2
#         assert "alpha, beta, rc" in result.output


def test_bump_command_no_version_file(cli_runner):
    """Test bump command when version file doesn't exist."""
    with cli_runner.isolated_filesystem():
        result = cli_runner.invoke(app, ["patch", "-m", "fix: test"])
        assert result.exit_code == 1
        assert "Version file not found" in result.output


def test_bump_command_no_changelog(cli_runner, test_files):
    """Test bump command when changelog doesn't exist."""
    with cli_runner.isolated_filesystem() as td:
        test_dir = Path(td)
        version_file = test_dir / "pyproject.toml"
        version_file.write_text('[project]\nversion = "0.1.0"\n')

        result = cli_runner.invoke(app, ["patch", "-m", "fix: test"])
        assert result.exit_code == 0, f"Command failed:\n{result.output}"

        changelog_file = test_dir / "CHANGELOG.md"
        assert changelog_file.exists()
        assert "## [0.1.1]" in changelog_file.read_text()


# [Other test functions remain the same...]
