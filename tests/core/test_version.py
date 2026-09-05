import json

import pytest
import tomli
import tomli_w
from packaging.version import InvalidVersion

from pezin.core.config import MonorepoConfig, ServiceConfig
from pezin.core.version import (
    ServiceVersionManager,
    Version,
    VersionBumpType,
    VersionFileConfig,
    VersionManager,
)


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


class TestVersionFileConfig:
    """Test VersionFileConfig dataclass."""

    def test_config_creation(self):
        """Test creating VersionFileConfig."""
        config = VersionFileConfig(
            path="pyproject.toml", file_type="toml", version_key="project.version"
        )

        assert config.path == "pyproject.toml"
        assert config.file_type == "toml"
        assert config.version_key == "project.version"
        assert config.encoding == "utf-8"

    def test_config_defaults(self):
        """Test VersionFileConfig defaults."""
        config = VersionFileConfig(path="version.txt")

        assert config.file_type is None
        assert config.version_key is None
        assert config.version_pattern is None
        assert config.version_replacement is None
        assert config.encoding == "utf-8"


class TestVersionManager:
    """Test VersionManager class."""

    def test_single_toml_file(self, tmp_path):
        """Test VersionManager with single TOML file."""
        toml_file = tmp_path / "pyproject.toml"
        data = {"project": {"version": "1.2.3"}}
        toml_file.write_text(tomli_w.dumps(data))

        config = VersionFileConfig(path=toml_file)
        manager = VersionManager([config])

        version = manager.get_primary_version()
        assert version is not None
        assert str(version) == "1.2.3"

    def test_single_json_file(self, tmp_path):
        """Test VersionManager with single JSON file."""
        json_file = tmp_path / "package.json"
        data = {"version": "2.1.0", "name": "test"}
        json_file.write_text(json.dumps(data, indent=2))

        config = VersionFileConfig(path=json_file, file_type="json")
        manager = VersionManager([config])

        version = manager.get_primary_version()
        assert version is not None
        assert str(version) == "2.1.0"

    def test_multiple_files(self, tmp_path):
        """Test VersionManager with multiple files."""
        # Create TOML file
        toml_file = tmp_path / "pyproject.toml"
        toml_data = {"project": {"version": "1.5.0"}}
        toml_file.write_text(tomli_w.dumps(toml_data))

        # Create JSON file
        json_file = tmp_path / "package.json"
        json_data = {"version": "1.5.0", "name": "test"}
        json_file.write_text(json.dumps(json_data, indent=2))

        configs = [
            VersionFileConfig(path=toml_file),
            VersionFileConfig(path=json_file, file_type="json"),
        ]
        manager = VersionManager(configs)

        # Test reading versions
        versions = manager.read_versions()
        assert len(versions) == 2
        assert all(str(v) == "1.5.0" for v in versions.values() if v)

        # Test version consistency
        assert manager.validate_version_consistency()

    def test_write_multiple_files(self, tmp_path):
        """Test writing to multiple files."""
        # Create TOML file
        toml_file = tmp_path / "pyproject.toml"
        toml_data = {"project": {"version": "1.0.0"}}
        toml_file.write_text(tomli_w.dumps(toml_data))

        # Create JSON file
        json_file = tmp_path / "package.json"
        json_data = {"version": "1.0.0", "name": "test"}
        json_file.write_text(json.dumps(json_data, indent=2))

        configs = [
            VersionFileConfig(path=toml_file),
            VersionFileConfig(path=json_file, file_type="json"),
        ]
        manager = VersionManager(configs)

        # Write new version
        new_version = Version("1.1.0")
        updated_files = manager.write_versions(new_version)

        assert len(updated_files) == 2
        assert str(toml_file) in updated_files
        assert str(json_file) in updated_files

        # Verify files were updated
        updated_toml = tomli.loads(toml_file.read_text())
        updated_json = json.loads(json_file.read_text())

        assert updated_toml["project"]["version"] == "1.1.0"
        assert updated_json["version"] == "1.1.0"
        assert updated_json["name"] == "test"  # Other fields preserved

    def test_version_inconsistency(self, tmp_path):
        """Test detection of version inconsistency."""
        # Create files with different versions
        toml_file = tmp_path / "pyproject.toml"
        toml_data = {"project": {"version": "1.0.0"}}
        toml_file.write_text(tomli_w.dumps(toml_data))

        json_file = tmp_path / "package.json"
        json_data = {"version": "2.0.0", "name": "test"}
        json_file.write_text(json.dumps(json_data, indent=2))

        configs = [
            VersionFileConfig(path=toml_file),
            VersionFileConfig(path=json_file, file_type="json"),
        ]
        manager = VersionManager(configs)

        assert not manager.validate_version_consistency()

    def test_from_config_legacy(self):
        """Test creating VersionManager from legacy config."""
        config = {"version_file": "pyproject.toml"}

        manager = VersionManager.from_config(config)
        assert len(manager.config_files) == 1
        assert str(manager.config_files[0].path) == "pyproject.toml"

    def test_from_config_multi_file(self):
        """Test creating VersionManager from multi-file config."""
        config = {
            "version_files": [
                {"path": "pyproject.toml", "file_type": "toml"},
                {"path": "package.json", "file_type": "json"},
                {
                    "path": "version.h",
                    "file_type": "generic",
                    "version_pattern": r'#define VERSION "([^"]+)"',
                    "version_replacement": r'#define VERSION "{version}"',
                },
            ]
        }

        manager = VersionManager.from_config(config)
        assert len(manager.config_files) == 3

        # Check TOML config
        toml_config = manager.config_files[0]
        assert str(toml_config.path) == "pyproject.toml"
        assert toml_config.file_type == "toml"

        # Check JSON config
        json_config = manager.config_files[1]
        assert str(json_config.path) == "package.json"
        assert json_config.file_type == "json"

        # Check generic config
        generic_config = manager.config_files[2]
        assert str(generic_config.path) == "version.h"
        assert generic_config.file_type == "generic"
        assert generic_config.version_pattern == r'#define VERSION "([^"]+)"'

    def test_from_config_simple_paths(self):
        """Test creating VersionManager from simple path strings."""
        config = {"version_files": ["pyproject.toml", "package.json"]}

        manager = VersionManager.from_config(config)
        assert len(manager.config_files) == 2
        assert str(manager.config_files[0].path) == "pyproject.toml"
        assert str(manager.config_files[1].path) == "package.json"

    def test_empty_config(self):
        """Test creating VersionManager with empty config."""
        config = {}

        manager = VersionManager.from_config(config)
        assert len(manager.config_files) == 1
        assert str(manager.config_files[0].path) == "pyproject.toml"  # Default fallback

    def test_generic_file_with_pattern(self, tmp_path):
        """Test VersionManager with generic file using custom pattern."""
        # Create a C header file
        header_file = tmp_path / "version.h"
        content = """#ifndef VERSION_H
#define VERSION_H

#define VERSION "1.2.3"

#endif
"""
        header_file.write_text(content)

        config = VersionFileConfig(
            path=header_file,
            file_type="generic",
            version_pattern=r'#define VERSION "([^"]+)"',
            version_replacement=r'#define VERSION "{version}"',
        )
        manager = VersionManager([config])

        # Test reading
        version = manager.get_primary_version()
        assert version is not None
        assert str(version) == "1.2.3"

        # Test writing
        new_version = Version("1.3.0")
        updated_files = manager.write_versions(new_version)
        assert len(updated_files) == 1

        # Verify content was updated
        updated_content = header_file.read_text()
        assert '#define VERSION "1.3.0"' in updated_content
        assert '#define VERSION "1.2.3"' not in updated_content


class TestServiceVersionManager:
    """Tests for ServiceVersionManager class."""

    def test_basic_creation(self, tmp_path):
        """Test creating ServiceVersionManager."""
        # Create version file for backend
        backend_toml = tmp_path / "backend" / "pyproject.toml"
        backend_toml.parent.mkdir(parents=True)
        backend_toml.write_text(tomli_w.dumps({"project": {"version": "1.0.0"}}))

        config = MonorepoConfig(
            services=[
                ServiceConfig(
                    name="backend",
                    version_files=[VersionFileConfig(path=backend_toml)],
                )
            ]
        )
        manager = ServiceVersionManager(config)
        assert "backend" in manager._service_managers

    def test_get_services_for_scopes(self, tmp_path):
        """Test mapping scopes to services."""
        # Create version files
        backend_toml = tmp_path / "backend" / "pyproject.toml"
        backend_toml.parent.mkdir(parents=True)
        backend_toml.write_text(tomli_w.dumps({"project": {"version": "1.0.0"}}))

        frontend_json = tmp_path / "frontend" / "package.json"
        frontend_json.parent.mkdir(parents=True)
        frontend_json.write_text(json.dumps({"version": "2.0.0"}))

        config = MonorepoConfig(
            services=[
                ServiceConfig(
                    name="backend",
                    version_files=[VersionFileConfig(path=backend_toml)],
                ),
                ServiceConfig(
                    name="frontend",
                    version_files=[
                        VersionFileConfig(path=frontend_json, file_type="json")
                    ],
                ),
            ]
        )
        manager = ServiceVersionManager(config)

        # Test single scope
        services, unknown = manager.get_services_for_scopes(["backend"])
        assert len(services) == 1
        assert services[0].name == "backend"
        assert len(unknown) == 0

        # Test multiple scopes
        services, unknown = manager.get_services_for_scopes(["backend", "frontend"])
        assert len(services) == 2

        # Test unknown scope
        services, unknown = manager.get_services_for_scopes(["unknown"])
        assert len(services) == 0
        assert unknown == ["unknown"]

    def test_get_default_service(self, tmp_path):
        """Test getting default service."""
        backend_toml = tmp_path / "pyproject.toml"
        backend_toml.write_text(tomli_w.dumps({"project": {"version": "1.0.0"}}))

        config = MonorepoConfig(
            services=[
                ServiceConfig(
                    name="backend",
                    version_files=[VersionFileConfig(path=backend_toml)],
                ),
            ],
            default_service="backend",
        )
        manager = ServiceVersionManager(config)

        default = manager.get_default_service()
        assert default is not None
        assert default.name == "backend"

    def test_get_default_service_not_set(self, tmp_path):
        """Test getting default service when not configured."""
        backend_toml = tmp_path / "pyproject.toml"
        backend_toml.write_text(tomli_w.dumps({"project": {"version": "1.0.0"}}))

        config = MonorepoConfig(
            services=[
                ServiceConfig(
                    name="backend",
                    version_files=[VersionFileConfig(path=backend_toml)],
                ),
            ]
        )
        manager = ServiceVersionManager(config)

        default = manager.get_default_service()
        assert default is None

    def test_bump_service(self, tmp_path):
        """Test bumping a single service version."""
        backend_toml = tmp_path / "backend" / "pyproject.toml"
        backend_toml.parent.mkdir(parents=True)
        backend_toml.write_text(tomli_w.dumps({"project": {"version": "1.0.0"}}))

        service = ServiceConfig(
            name="backend",
            version_files=[VersionFileConfig(path=backend_toml)],
        )
        config = MonorepoConfig(services=[service])
        manager = ServiceVersionManager(config)

        result = manager.bump_service(service, VersionBumpType.MINOR)
        assert result is not None
        assert result.service_name == "backend"
        assert str(result.old_version) == "1.0.0"
        assert str(result.new_version) == "1.1.0"
        assert result.tag_name == "backend-v1.1.0"
        assert len(result.updated_files) == 1

        # Verify file was updated
        updated = tomli.loads(backend_toml.read_text())
        assert updated["project"]["version"] == "1.1.0"

    def test_bump_services_multiple(self, tmp_path):
        """Test bumping multiple services."""
        # Create backend version file
        backend_toml = tmp_path / "backend" / "pyproject.toml"
        backend_toml.parent.mkdir(parents=True)
        backend_toml.write_text(tomli_w.dumps({"project": {"version": "1.0.0"}}))

        # Create frontend version file
        frontend_json = tmp_path / "frontend" / "package.json"
        frontend_json.parent.mkdir(parents=True)
        frontend_json.write_text(json.dumps({"version": "2.0.0"}))

        backend_service = ServiceConfig(
            name="backend",
            version_files=[VersionFileConfig(path=backend_toml)],
        )
        frontend_service = ServiceConfig(
            name="frontend",
            version_files=[VersionFileConfig(path=frontend_json, file_type="json")],
        )
        config = MonorepoConfig(services=[backend_service, frontend_service])
        manager = ServiceVersionManager(config)

        results = manager.bump_services(
            [backend_service, frontend_service], VersionBumpType.PATCH
        )
        assert len(results) == 2

        # Check backend
        backend_result = next(r for r in results if r.service_name == "backend")
        assert str(backend_result.new_version) == "1.0.1"

        # Check frontend
        frontend_result = next(r for r in results if r.service_name == "frontend")
        assert str(frontend_result.new_version) == "2.0.1"

    def test_bump_service_with_prerelease(self, tmp_path):
        """Test bumping service with prerelease label."""
        backend_toml = tmp_path / "pyproject.toml"
        backend_toml.write_text(tomli_w.dumps({"project": {"version": "1.0.0"}}))

        service = ServiceConfig(
            name="backend",
            version_files=[VersionFileConfig(path=backend_toml)],
        )
        config = MonorepoConfig(services=[service])
        manager = ServiceVersionManager(config)

        result = manager.bump_service(
            service, VersionBumpType.MAJOR, prerelease="alpha"
        )
        assert str(result.new_version) == "2.0.0-alpha"

    def test_bump_service_custom_tag_prefix(self, tmp_path):
        """Test bumping service with custom tag prefix."""
        backend_toml = tmp_path / "pyproject.toml"
        backend_toml.write_text(tomli_w.dumps({"project": {"version": "1.0.0"}}))

        service = ServiceConfig(
            name="backend",
            version_files=[VersionFileConfig(path=backend_toml)],
            tag_prefix="be-release-",
        )
        config = MonorepoConfig(services=[service])
        manager = ServiceVersionManager(config)

        result = manager.bump_service(service, VersionBumpType.PATCH)
        assert result.tag_name == "be-release-1.0.1"

    def test_from_config(self, tmp_path):
        """Test creating ServiceVersionManager from config dict."""
        backend_toml = tmp_path / "backend" / "pyproject.toml"
        backend_toml.parent.mkdir(parents=True)
        backend_toml.write_text(tomli_w.dumps({"project": {"version": "1.0.0"}}))

        config_dict = {
            "mode": "monorepo",
            "services": [
                {
                    "name": "backend",
                    "version_files": [{"path": str(backend_toml)}],
                },
            ],
            "default_service": "backend",
            "require_scope": True,
        }

        manager = ServiceVersionManager.from_config(config_dict)
        assert len(manager.config.services) == 1
        assert manager.config.default_service == "backend"
        assert manager.config.require_scope is True

    def test_bump_nonexistent_service(self, tmp_path):
        """Test bumping a service that doesn't have a manager."""
        backend_toml = tmp_path / "pyproject.toml"
        backend_toml.write_text(tomli_w.dumps({"project": {"version": "1.0.0"}}))

        # Create service without version files
        service = ServiceConfig(name="empty", version_files=[])
        config = MonorepoConfig(services=[service])
        manager = ServiceVersionManager(config)

        result = manager.bump_service(service, VersionBumpType.MINOR)
        assert result is None
