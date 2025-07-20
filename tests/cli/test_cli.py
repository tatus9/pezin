"""CLI test suite."""

import re
from pathlib import Path

import pytest
import tomli
from typer.testing import CliRunner

from pezin.cli.main import app

# Test logging is handled by pytest configuration


def strip_ansi_codes(text: str) -> str:
    """Strip ANSI color codes from text to make tests CI-compatible."""
    ansi_escape = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")
    return ansi_escape.sub("", text)


@pytest.fixture
def cli_runner():
    """Fixture providing a Typer CLI test runner."""
    return CliRunner()


@pytest.fixture
def test_files(tmp_path: Path):
    """Create and copy test files to a directory."""

    def _create_files(path: Path, copy_defaults: bool = True):
        path.mkdir(parents=True, exist_ok=True)
        # Creating test files in specified path

        if copy_defaults:
            # Create version file
            version_file = path / "pyproject.toml"
            version_file.write_text('[project]\nversion = "0.1.0"\n')

            # Create changelog file
            changelog_file = path / "CHANGELOG.md"
            changelog_file.write_text("# Changelog\n\n## [Unreleased]\n")

        return path

    return _create_files


@pytest.fixture
def test_project_files(tmp_path: Path):
    """Create test project files for version detection testing."""

    def _create_project(
        project_type: str, name: str = "test-project", version: str = "1.2.3"
    ):
        project_dir = tmp_path / "test_project"
        project_dir.mkdir(exist_ok=True)

        if project_type == "pyproject":
            config_file = project_dir / "pyproject.toml"
            config_file.write_text(f'''[project]
name = "{name}"
version = "{version}"
''')
        elif project_type == "package_json":
            config_file = project_dir / "package.json"
            import json

            config_file.write_text(json.dumps({"name": name, "version": version}))
        elif project_type == "pezin_toml":
            config_file = project_dir / "pezin.toml"
            config_file.write_text(f'''[project]
name = "{name}"
version = "{version}"
''')

        return project_dir, config_file

    return _create_project


def test_cli_help(cli_runner):
    """Test CLI help output."""
    result = cli_runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "Usage:" in result.output
    assert "major" in result.output
    assert "minor" in result.output
    assert "patch" in result.output


def test_bump_command_help(cli_runner):
    """Test bump command help output."""
    result = cli_runner.invoke(app, ["patch", "--help"])
    assert result.exit_code == 0
    # Strip ANSI codes to handle colored output in CI environments
    clean_output = strip_ansi_codes(result.output)
    assert "--message" in clean_output
    assert "--pre" in clean_output


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
        config_file = test_dir / "pezin.toml"
        config_file.write_text("""
[project]
version = "0.1.0"

[pezin]
changelog_file = "custom_changelog.md"
""")

        # Create changelog file
        changelog_file = test_dir / "custom_changelog.md"
        changelog_file.write_text("# Changelog\n\n## [Unreleased]\n")

        # Test directory setup with config file

        result = cli_runner.invoke(
            app, ["patch", "--config", str(config_file), "-m", "fix: config test"]
        )
        if result.exit_code != 0:
            print(f"Command output:\n{result.output}")

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
        config_file = test_dir / "pezin.toml"
        config_file.write_text("""
[pezin]
version_file = "VERSION"
changelog_file = "CHANGES.md"
""")

        # Create changelog file
        changelog_file = test_dir / "CHANGES.md"
        changelog_file.write_text("# Changelog\n\n## [Unreleased]\n")

        # Test directory setup with external version file

        result = cli_runner.invoke(
            app, ["patch", "--config", str(config_file), "-m", "fix: external version"]
        )
        if result.exit_code != 0:
            print(f"Command output:\n{result.output}")

        assert result.exit_code == 0, f"Command failed:\n{result.output}"

        # Verify changes
        assert version_file.read_text().strip() == "0.1.1"
        assert "## [0.1.1]" in changelog_file.read_text()
        assert "external version" in changelog_file.read_text()


def test_bump_command_valid_prerelease(cli_runner, test_files):
    """Test bump command with valid pre-release label."""
    with cli_runner.isolated_filesystem() as td:
        test_dir = Path(td)
        version_file = test_dir / "pyproject.toml"
        version_file.write_text('[project]\nversion = "0.1.0"\n')

        changelog_file = test_dir / "CHANGELOG.md"
        changelog_file.write_text("# Changelog\n\n## [Unreleased]\n")

        result = cli_runner.invoke(
            app, ["patch", "--pre", "beta", "-m", "fix: test with beta"]
        )
        assert result.exit_code == 0

        # Verify version bump with prerelease
        with open(version_file, "rb") as f:
            config = tomli.load(f)
        assert config["project"]["version"] == "0.1.1-beta"


def test_bump_command_invalid_prerelease(cli_runner, test_files):
    """Test bump command with invalid pre-release label."""
    with cli_runner.isolated_filesystem() as td:
        test_dir = Path(td)
        version_file = test_dir / "pyproject.toml"
        version_file.write_text('[project]\nversion = "0.1.0"\n')

        result = cli_runner.invoke(
            app, ["patch", "--pre", "invalid", "-m", "fix: test"]
        )
        assert result.exit_code == 2
        assert "alpha, beta, rc" in result.output


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


def test_version_flag_clean_output(cli_runner):
    """Test that -v flag produces clean output without logs."""
    result = cli_runner.invoke(app, ["-v"])
    assert result.exit_code == 0
    # Should only contain version line, no logging output
    lines = [line for line in result.output.strip().split("\n") if line.strip()]
    assert len(lines) >= 1
    assert "pezin" in lines[-1]  # Last line should be pezin version
    # Should not contain logging messages
    assert "INFO" not in result.output
    assert "DEBUG" not in result.output
    assert "Found config file" not in result.output


def test_version_command_clean_output(cli_runner):
    """Test that version subcommand produces clean output without logs."""
    result = cli_runner.invoke(app, ["version"])
    assert result.exit_code == 0
    # Should only contain version line, no logging output
    lines = [line for line in result.output.strip().split("\n") if line.strip()]
    assert len(lines) >= 1
    assert "pezin" in lines[-1]  # Last line should be pezin version
    # Should not contain logging messages
    assert "INFO" not in result.output
    assert "DEBUG" not in result.output
    assert "Found config file" not in result.output


def test_version_flag_vs_version_command_consistency(cli_runner):
    """Test that -v flag and version command produce identical output."""
    result_flag = cli_runner.invoke(app, ["-v"])
    result_command = cli_runner.invoke(app, ["version"])

    assert result_flag.exit_code == 0
    assert result_command.exit_code == 0
    assert result_flag.output == result_command.output


def test_project_version_detection_functions(test_project_files):
    """Test the project version detection functions work correctly."""
    import os

    from pezin.cli.main import get_current_project_info, get_version_quietly

    # Test pyproject.toml detection
    project_dir, config_file = test_project_files("pyproject", "my-project", "2.1.0")

    # Change to project directory for testing
    original_cwd = os.getcwd()
    try:
        os.chdir(project_dir)

        # Test quiet version reading
        version = get_version_quietly(config_file)
        assert version == "2.1.0"

        # Test project info detection
        name, version = get_current_project_info()
        assert name == "my-project"
        assert version == "2.1.0"

    finally:
        os.chdir(original_cwd)


def test_project_version_detection_package_json(test_project_files):
    """Test version detection with package.json files."""
    import os

    from pezin.cli.main import get_current_project_info, get_version_quietly

    # Test package.json detection
    project_dir, config_file = test_project_files(
        "package_json", "my-node-project", "3.2.1"
    )

    # Change to project directory for testing
    original_cwd = os.getcwd()
    try:
        os.chdir(project_dir)

        # Test quiet version reading
        version = get_version_quietly(config_file)
        assert version == "3.2.1"

        # Test project info detection
        name, version = get_current_project_info()
        assert name == "my-node-project"
        assert version == "3.2.1"

    finally:
        os.chdir(original_cwd)


def test_project_version_detection_no_config(tmp_path):
    """Test version detection when no config file exists."""
    import os

    from pezin.cli.main import get_current_project_info

    # Create empty directory
    empty_dir = tmp_path / "empty"
    empty_dir.mkdir()

    original_cwd = os.getcwd()
    try:
        os.chdir(empty_dir)

        # Should return None, None when no config found
        name, version = get_current_project_info()
        assert name is None
        assert version is None

    finally:
        os.chdir(original_cwd)
