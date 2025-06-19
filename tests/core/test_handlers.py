"""Tests for file handlers."""

import json
from pathlib import Path

import tomli
import tomli_w

from pumper.core.handlers import (
    COMMON_PATTERNS,
    FileHandlerFactory,
    GenericFileHandler,
    JsonFileHandler,
    TomlFileHandler,
)
from pumper.core.version import Version


class TestTomlFileHandler:
    """Test TOML file handler."""

    def test_read_version_project_section(self, tmp_path):
        """Test reading version from [project] section."""
        toml_file = tmp_path / "pyproject.toml"
        data = {"project": {"version": "1.2.3"}}
        toml_file.write_text(tomli_w.dumps(data))

        handler = TomlFileHandler(toml_file)
        version = handler.read_version()

        assert version is not None
        assert str(version) == "1.2.3"

    def test_read_version_pumper_section(self, tmp_path):
        """Test reading version from [pumper] section."""
        toml_file = tmp_path / "config.toml"
        data = {"pumper": {"version": "2.1.0"}}
        toml_file.write_text(tomli_w.dumps(data))

        handler = TomlFileHandler(toml_file)
        version = handler.read_version()

        assert version is not None
        assert str(version) == "2.1.0"

    def test_read_version_tool_pumper_section(self, tmp_path):
        """Test reading version from [tool.pumper] section."""
        toml_file = tmp_path / "config.toml"
        data = {"tool": {"pumper": {"version": "0.5.0"}}}
        toml_file.write_text(tomli_w.dumps(data))

        handler = TomlFileHandler(toml_file)
        version = handler.read_version()

        assert version is not None
        assert str(version) == "0.5.0"

    def test_read_version_custom_keys(self, tmp_path):
        """Test reading version with custom keys."""
        toml_file = tmp_path / "config.toml"
        data = {"app": {"version": "3.0.0"}}
        toml_file.write_text(tomli_w.dumps(data))

        handler = TomlFileHandler(toml_file, version_keys=["app.version"])
        version = handler.read_version()

        assert version is not None
        assert str(version) == "3.0.0"

    def test_write_version_existing_section(self, tmp_path):
        """Test writing version to existing section."""
        toml_file = tmp_path / "pyproject.toml"
        data = {"project": {"version": "1.0.0", "name": "test"}}
        toml_file.write_text(tomli_w.dumps(data))

        handler = TomlFileHandler(toml_file)
        handler.read_version()  # Set _found_key
        handler.write_version(Version("1.1.0"))

        updated_data = tomli.loads(toml_file.read_text())
        assert updated_data["project"]["version"] == "1.1.0"
        assert updated_data["project"]["name"] == "test"

    def test_write_version_new_section(self, tmp_path):
        """Test writing version to new section."""
        toml_file = tmp_path / "new.toml"
        toml_file.write_text("")

        handler = TomlFileHandler(toml_file)
        handler.write_version(Version("1.0.0"))

        updated_data = tomli.loads(toml_file.read_text())
        assert updated_data["project"]["version"] == "1.0.0"

    def test_supports_file(self):
        """Test file support detection."""
        handler = TomlFileHandler(Path("dummy"))

        assert handler.supports_file("pyproject.toml")
        assert handler.supports_file("config.toml")
        assert handler.supports_file("Pipfile")
        assert not handler.supports_file("package.json")
        assert not handler.supports_file("version.txt")

    def test_read_nonexistent_file(self, tmp_path):
        """Test reading from non-existent file."""
        toml_file = tmp_path / "nonexistent.toml"
        handler = TomlFileHandler(toml_file)

        assert handler.read_version() is None


class TestJsonFileHandler:
    """Test JSON file handler."""

    def test_read_version_default_key(self, tmp_path):
        """Test reading version from default 'version' key."""
        json_file = tmp_path / "package.json"
        data = {"version": "1.2.3", "name": "test-package"}
        json_file.write_text(json.dumps(data, indent=2))

        handler = JsonFileHandler(json_file)
        version = handler.read_version()

        assert version is not None
        assert str(version) == "1.2.3"

    def test_read_version_custom_key(self, tmp_path):
        """Test reading version from custom key."""
        json_file = tmp_path / "config.json"
        data = {"app": {"version": "2.1.0"}}
        json_file.write_text(json.dumps(data, indent=2))

        handler = JsonFileHandler(json_file, version_key="app.version")
        version = handler.read_version()

        assert version is not None
        assert str(version) == "2.1.0"

    def test_write_version_existing_key(self, tmp_path):
        """Test writing version to existing key."""
        json_file = tmp_path / "package.json"
        data = {"version": "1.0.0", "name": "test-package"}
        json_file.write_text(json.dumps(data, indent=2))

        handler = JsonFileHandler(json_file)
        handler.write_version(Version("1.1.0"))

        updated_data = json.loads(json_file.read_text())
        assert updated_data["version"] == "1.1.0"
        assert updated_data["name"] == "test-package"

    def test_write_version_new_key(self, tmp_path):
        """Test writing version to new key."""
        json_file = tmp_path / "config.json"
        data = {"name": "test"}
        json_file.write_text(json.dumps(data, indent=2))

        handler = JsonFileHandler(json_file)
        handler.write_version(Version("1.0.0"))

        updated_data = json.loads(json_file.read_text())
        assert updated_data["version"] == "1.0.0"
        assert updated_data["name"] == "test"

    def test_supports_file(self):
        """Test file support detection."""
        handler = JsonFileHandler(Path("dummy"))

        assert handler.supports_file("package.json")
        assert handler.supports_file("composer.json")
        assert handler.supports_file("config.json")
        assert not handler.supports_file("pyproject.toml")
        assert not handler.supports_file("version.txt")

    def test_read_nonexistent_file(self, tmp_path):
        """Test reading from non-existent file."""
        json_file = tmp_path / "nonexistent.json"
        handler = JsonFileHandler(json_file)

        assert handler.read_version() is None


class TestGenericFileHandler:
    """Test generic file handler."""

    def test_read_version_c_header(self, tmp_path):
        """Test reading version from C header file."""
        header_file = tmp_path / "version.h"
        content = """#ifndef VERSION_H
#define VERSION_H

#define VERSION "1.2.3"

#endif
"""
        header_file.write_text(content)

        pattern = COMMON_PATTERNS["c_header"]["pattern"]
        handler = GenericFileHandler(header_file, pattern)
        version = handler.read_version()

        assert version is not None
        assert str(version) == "1.2.3"

    def test_write_version_c_header(self, tmp_path):
        """Test writing version to C header file."""
        header_file = tmp_path / "version.h"
        content = """#ifndef VERSION_H
#define VERSION_H

#define VERSION "1.0.0"

#endif
"""
        header_file.write_text(content)

        pattern = COMMON_PATTERNS["c_header"]["pattern"]
        replacement = COMMON_PATTERNS["c_header"]["replacement"]
        handler = GenericFileHandler(header_file, pattern, replacement)
        handler.write_version(Version("1.1.0"))

        updated_content = header_file.read_text()
        assert '#define VERSION "1.1.0"' in updated_content
        assert '#define VERSION "1.0.0"' not in updated_content

    def test_read_version_makefile(self, tmp_path):
        """Test reading version from Makefile."""
        makefile = tmp_path / "Makefile"
        content = """PROJECT = test
VERSION = 2.5.0
CC = gcc
"""
        makefile.write_text(content)

        pattern = COMMON_PATTERNS["makefile"]["pattern"]
        handler = GenericFileHandler(makefile, pattern)
        version = handler.read_version()

        assert version is not None
        assert str(version) == "2.5.0"

    def test_write_version_makefile(self, tmp_path):
        """Test writing version to Makefile."""
        makefile = tmp_path / "Makefile"
        content = """PROJECT = test
VERSION = 2.5.0
CC = gcc
"""
        makefile.write_text(content)

        pattern = COMMON_PATTERNS["makefile"]["pattern"]
        replacement = COMMON_PATTERNS["makefile"]["replacement"]
        handler = GenericFileHandler(makefile, pattern, replacement)
        handler.write_version(Version("2.6.0"))

        updated_content = makefile.read_text()
        assert "VERSION = 2.6.0" in updated_content
        assert "VERSION = 2.5.0" not in updated_content

    def test_supports_file(self):
        """Test file support detection."""
        handler = GenericFileHandler(Path("dummy"), r".*")

        # Generic handler supports all files
        assert handler.supports_file("any.txt")
        assert handler.supports_file("version.h")
        assert handler.supports_file("Makefile")

    def test_read_nonexistent_file(self, tmp_path):
        """Test reading from non-existent file."""
        text_file = tmp_path / "nonexistent.txt"
        handler = GenericFileHandler(text_file, r"version\s*=\s*(.+)")

        assert handler.read_version() is None


class TestFileHandlerFactory:
    """Test file handler factory."""

    def test_create_toml_handler(self, tmp_path):
        """Test creating TOML handler."""
        toml_file = tmp_path / "pyproject.toml"
        handler = FileHandlerFactory.create_handler(toml_file)

        assert isinstance(handler, TomlFileHandler)

    def test_create_json_handler(self, tmp_path):
        """Test creating JSON handler."""
        json_file = tmp_path / "package.json"
        handler = FileHandlerFactory.create_handler(json_file)

        assert isinstance(handler, JsonFileHandler)

    def test_create_generic_handler(self, tmp_path):
        """Test creating generic handler."""
        text_file = tmp_path / "version.txt"
        handler = FileHandlerFactory.create_handler(text_file)

        assert isinstance(handler, GenericFileHandler)

    def test_create_explicit_type(self, tmp_path):
        """Test creating handler with explicit type."""
        file_path = tmp_path / "config.txt"
        handler = FileHandlerFactory.create_handler(file_path, "json")

        assert isinstance(handler, JsonFileHandler)

    def test_create_with_kwargs(self, tmp_path):
        """Test creating handler with additional kwargs."""
        json_file = tmp_path / "config.json"
        handler = FileHandlerFactory.create_handler(
            json_file, "json", version_key="app.version"
        )

        assert isinstance(handler, JsonFileHandler)
        assert handler.version_key == "app.version"

    def test_get_supported_handlers(self):
        """Test getting supported handler types."""
        handlers = FileHandlerFactory.get_supported_handlers()

        assert "toml" in handlers
        assert "json" in handlers
        assert "generic" in handlers


class TestCommonPatterns:
    """Test common patterns for different file types."""

    def test_c_header_pattern(self, tmp_path):
        """Test C header pattern."""
        header_file = tmp_path / "version.h"
        content = '#define VERSION "1.2.3"'
        header_file.write_text(content)

        pattern = COMMON_PATTERNS["c_header"]["pattern"]
        handler = GenericFileHandler(header_file, pattern)
        version = handler.read_version()

        assert version is not None
        assert str(version) == "1.2.3"

    def test_cmake_pattern(self, tmp_path):
        """Test CMake pattern."""
        cmake_file = tmp_path / "CMakeLists.txt"
        content = "project(MyProject VERSION 1.2.3)"
        cmake_file.write_text(content)

        pattern = COMMON_PATTERNS["cmake"]["pattern"]
        handler = GenericFileHandler(cmake_file, pattern)
        version = handler.read_version()

        assert version is not None
        assert str(version) == "1.2.3"

    def test_dockerfile_pattern(self, tmp_path):
        """Test Dockerfile pattern."""
        dockerfile = tmp_path / "Dockerfile"
        content = 'LABEL version="1.2.3"'
        dockerfile.write_text(content)

        pattern = COMMON_PATTERNS["dockerfile"]["pattern"]
        handler = GenericFileHandler(dockerfile, pattern)
        version = handler.read_version()

        assert version is not None
        assert str(version) == "1.2.3"

    def test_shell_script_pattern(self, tmp_path):
        """Test shell script pattern."""
        script_file = tmp_path / "script.sh"
        content = 'VERSION="1.2.3"'
        script_file.write_text(content)

        pattern = COMMON_PATTERNS["shell_script"]["pattern"]
        handler = GenericFileHandler(script_file, pattern)
        version = handler.read_version()

        assert version is not None
        assert str(version) == "1.2.3"
