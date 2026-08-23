"""Tests for monorepo configuration module."""

from pezin.core.config import (
    ChangelogHookConfig,
    MonorepoConfig,
    ServiceConfig,
    is_monorepo_mode,
    read_changelog_config,
)
from pezin.core.version import VersionFileConfig


class TestServiceConfig:
    """Tests for ServiceConfig dataclass."""

    def test_basic_creation(self):
        """Test creating a basic service config."""
        config = ServiceConfig(
            name="backend",
            version_files=[VersionFileConfig(path="backend/pyproject.toml")],
        )
        assert config.name == "backend"
        assert len(config.version_files) == 1
        assert config.tag_prefix is None

    def test_custom_tag_prefix(self):
        """Test service with custom tag prefix."""
        config = ServiceConfig(
            name="backend",
            version_files=[],
            tag_prefix="be-v",
        )
        assert config.get_tag_name("1.2.3") == "be-v1.2.3"

    def test_default_tag_prefix(self):
        """Test default tag prefix uses service name."""
        config = ServiceConfig(name="local_server", version_files=[])
        assert config.get_tag_name("2.0.0") == "local_server-v2.0.0"

    def test_from_dict_basic(self):
        """Test creating service from dictionary."""
        data = {
            "name": "backend",
            "version_files": [{"path": "backend/pyproject.toml"}],
        }
        config = ServiceConfig.from_dict(data)
        assert config.name == "backend"
        assert len(config.version_files) == 1
        assert str(config.version_files[0].path) == "backend/pyproject.toml"

    def test_from_dict_with_file_type(self):
        """Test creating service with file type specified."""
        data = {
            "name": "frontend",
            "version_files": [
                {"path": "package.json", "file_type": "json"},
            ],
        }
        config = ServiceConfig.from_dict(data)
        assert config.version_files[0].file_type == "json"

    def test_from_dict_with_tag_prefix(self):
        """Test creating service with custom tag prefix."""
        data = {
            "name": "api",
            "version_files": [],
            "tag_prefix": "api-release-",
        }
        config = ServiceConfig.from_dict(data)
        assert config.tag_prefix == "api-release-"
        assert config.get_tag_name("1.0.0") == "api-release-1.0.0"

    def test_from_dict_string_paths(self):
        """Test creating service with simple string paths."""
        data = {
            "name": "backend",
            "version_files": ["pyproject.toml"],
        }
        config = ServiceConfig.from_dict(data)
        assert len(config.version_files) == 1
        assert str(config.version_files[0].path) == "pyproject.toml"


class TestMonorepoConfig:
    """Tests for MonorepoConfig dataclass."""

    def test_basic_creation(self):
        """Test creating basic monorepo config."""
        config = MonorepoConfig(
            services=[
                ServiceConfig(name="backend", version_files=[]),
                ServiceConfig(name="frontend", version_files=[]),
            ]
        )
        assert len(config.services) == 2
        assert config.default_service is None
        assert config.require_scope is False

    def test_get_service(self):
        """Test getting service by name."""
        config = MonorepoConfig(
            services=[
                ServiceConfig(name="backend", version_files=[]),
                ServiceConfig(name="frontend", version_files=[]),
            ]
        )
        assert config.get_service("backend") is not None
        assert config.get_service("backend").name == "backend"
        assert config.get_service("nonexistent") is None

    def test_get_services_for_scopes_single(self):
        """Test mapping single scope to service."""
        config = MonorepoConfig(
            services=[
                ServiceConfig(name="backend", version_files=[]),
                ServiceConfig(name="frontend", version_files=[]),
            ]
        )
        services = config.get_services_for_scopes(["backend"])
        assert len(services) == 1
        assert services[0].name == "backend"

    def test_get_services_for_scopes_multiple(self):
        """Test mapping multiple scopes to services."""
        config = MonorepoConfig(
            services=[
                ServiceConfig(name="backend", version_files=[]),
                ServiceConfig(name="frontend", version_files=[]),
                ServiceConfig(name="api", version_files=[]),
            ]
        )
        services = config.get_services_for_scopes(["backend", "api"])
        assert len(services) == 2
        names = [s.name for s in services]
        assert "backend" in names
        assert "api" in names

    def test_get_services_for_scopes_deduplicates(self):
        """Test that duplicate scopes are deduplicated."""
        config = MonorepoConfig(
            services=[ServiceConfig(name="backend", version_files=[])]
        )
        services = config.get_services_for_scopes(["backend", "backend", "backend"])
        assert len(services) == 1

    def test_get_services_for_scopes_unknown_ignored(self):
        """Test that unknown scopes don't match any service."""
        config = MonorepoConfig(
            services=[ServiceConfig(name="backend", version_files=[])]
        )
        services = config.get_services_for_scopes(["unknown"])
        assert len(services) == 0

    def test_get_services_for_scopes_empty(self):
        """Test handling empty scopes list."""
        config = MonorepoConfig(
            services=[ServiceConfig(name="backend", version_files=[])]
        )
        services = config.get_services_for_scopes([])
        assert len(services) == 0

    def test_from_dict_basic(self):
        """Test creating config from dictionary."""
        data = {
            "services": [
                {
                    "name": "backend",
                    "version_files": [{"path": "backend/pyproject.toml"}],
                },
                {"name": "frontend", "version_files": [{"path": "package.json"}]},
            ]
        }
        config = MonorepoConfig.from_dict(data)
        assert len(config.services) == 2
        assert config.services[0].name == "backend"
        assert config.services[1].name == "frontend"

    def test_from_dict_with_options(self):
        """Test creating config with all options."""
        data = {
            "services": [
                {"name": "backend", "version_files": []},
            ],
            "default_service": "backend",
            "require_scope": True,
        }
        config = MonorepoConfig.from_dict(data)
        assert config.default_service == "backend"
        assert config.require_scope is True

    def test_from_dict_empty_services(self):
        """Test creating config with empty services."""
        data = {"services": []}
        config = MonorepoConfig.from_dict(data)
        assert len(config.services) == 0


class TestIsMonorepoMode:
    """Tests for is_monorepo_mode helper function."""

    def test_monorepo_mode_enabled(self):
        """Test detecting monorepo mode when enabled."""
        config = {"mode": "monorepo"}
        assert is_monorepo_mode(config) is True

    def test_monorepo_mode_disabled(self):
        """Test detecting single mode."""
        config = {"mode": "single"}
        assert is_monorepo_mode(config) is False

    def test_no_mode_key(self):
        """Test default behavior when mode key is missing."""
        config = {}
        assert is_monorepo_mode(config) is False

    def test_other_mode_value(self):
        """Test handling other mode values."""
        config = {"mode": "other"}
        assert is_monorepo_mode(config) is False


class TestChangelogHookConfig:
    """Tests for ChangelogHookConfig dataclass and resolver."""

    def test_missing_table_returns_defaults(self):
        cfg = read_changelog_config({})
        assert cfg == ChangelogHookConfig()
        assert cfg.enabled is True
        assert cfg.path == "CHANGELOG.md"
        assert cfg.unreleased_label == "Unreleased"

    def test_none_config_returns_defaults(self):
        cfg = read_changelog_config(None)
        assert cfg == ChangelogHookConfig()

    def test_partial_table_fills_defaults(self):
        cfg = read_changelog_config({"changelog": {"path": "docs/HISTORY.md"}})
        assert cfg.path == "docs/HISTORY.md"
        assert cfg.enabled is True
        assert cfg.unreleased_label == "Unreleased"

    def test_enabled_false_disables(self):
        cfg = read_changelog_config({"changelog": {"enabled": False}})
        assert cfg.enabled is False
        assert cfg.path == "CHANGELOG.md"

    def test_service_override_beats_top_level(self):
        pezin_config = {
            "changelog": {"path": "TOP.md", "enabled": True},
            "services": [
                {"name": "api", "changelog": {"path": "api/CHANGELOG.md"}},
                {"name": "web", "changelog": {"enabled": False}},
            ],
        }

        api_cfg = read_changelog_config(pezin_config, service_name="api")
        assert api_cfg.path == "api/CHANGELOG.md"
        assert api_cfg.enabled is True  # inherited from top-level

        web_cfg = read_changelog_config(pezin_config, service_name="web")
        assert web_cfg.enabled is False
        assert web_cfg.path == "TOP.md"  # inherited from top-level

        unknown_cfg = read_changelog_config(pezin_config, service_name="missing")
        assert unknown_cfg.path == "TOP.md"  # falls back to top-level
        assert unknown_cfg.enabled is True

    def test_service_without_changelog_uses_top_level(self):
        pezin_config = {
            "changelog": {"path": "TOP.md"},
            "services": [{"name": "api"}],
        }
        cfg = read_changelog_config(pezin_config, service_name="api")
        assert cfg.path == "TOP.md"
