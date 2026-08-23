"""Configuration models for Pezin.

This module provides dataclasses for configuring Pezin in both single-repo
and monorepo modes.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .version import VersionFileConfig


@dataclass
class ChangelogHookConfig:
    """Configuration for the post-commit changelog write.

    Attributes:
        enabled: Skip the changelog write entirely when False.
        path: Path to the changelog file (resolved relative to the repo or service root).
        unreleased_label: Header label used for the in-progress section.
    """

    enabled: bool = True
    path: str = "CHANGELOG.md"
    unreleased_label: str = "Unreleased"

    @classmethod
    def from_dict(cls, data: Optional[Dict[str, Any]] = None) -> "ChangelogHookConfig":
        """Build config from raw dict, filling missing keys with defaults."""
        data = data or {}
        defaults = cls()
        return cls(
            enabled=bool(data.get("enabled", defaults.enabled)),
            path=str(data.get("path", defaults.path)),
            unreleased_label=str(
                data.get("unreleased_label", defaults.unreleased_label)
            ),
        )


def read_changelog_config(
    pezin_config: Optional[Dict[str, Any]],
    service_name: Optional[str] = None,
) -> ChangelogHookConfig:
    """Resolve changelog hook config from a pezin config dictionary.

    Service-level overrides under `[tool.pezin.services.<name>.changelog]`
    win key-by-key over the top-level `[tool.pezin.changelog]` defaults.
    Missing tables yield an all-defaults config.
    """
    pezin_config = pezin_config or {}
    top_level = pezin_config.get("changelog") or {}

    if service_name:
        services = pezin_config.get("services") or []
        service_entry: Dict[str, Any] = {}
        for entry in services:
            if isinstance(entry, dict) and entry.get("name") == service_name:
                service_entry = entry
                break
        service_changelog = service_entry.get("changelog") or {}
        merged = {**top_level, **service_changelog}
        return ChangelogHookConfig.from_dict(merged)

    return ChangelogHookConfig.from_dict(top_level)


@dataclass
class ServiceConfig:
    """Configuration for a monorepo service.

    Represents a single service within a monorepo that has its own
    independent version management.

    Attributes:
        name: Service identifier used in commit scopes (e.g., "backend", "local_server")
        version_files: List of version file configurations for this service
        tag_prefix: Prefix for git tags (default: "{name}-v", e.g., "backend-v1.2.3")
    """

    name: str
    version_files: List[VersionFileConfig] = field(default_factory=list)
    tag_prefix: Optional[str] = None

    def get_tag_name(self, version: str) -> str:
        """Generate tag name for a version.

        Args:
            version: Version string (e.g., "1.2.3")

        Returns:
            Full tag name (e.g., "backend-v1.2.3")
        """
        prefix = self.tag_prefix or f"{self.name}-v"
        return f"{prefix}{version}"

    @classmethod
    def from_dict(cls, data: Dict) -> "ServiceConfig":
        """Create ServiceConfig from dictionary.

        Args:
            data: Dictionary with service configuration

        Returns:
            ServiceConfig instance
        """
        version_files = []
        for file_config in data.get("version_files", []):
            if isinstance(file_config, str):
                version_files.append(VersionFileConfig(path=file_config))
            else:
                version_files.append(VersionFileConfig(**file_config))

        return cls(
            name=data["name"],
            version_files=version_files,
            tag_prefix=data.get("tag_prefix"),
        )


@dataclass
class MonorepoConfig:
    """Configuration for monorepo mode.

    Manages multiple services with independent versioning within a single
    git repository.

    Attributes:
        services: List of service configurations
        default_service: Service to bump when commit has no scope (optional)
        require_scope: If True, fail when commit has no scope in monorepo mode
    """

    services: List[ServiceConfig] = field(default_factory=list)
    default_service: Optional[str] = None
    require_scope: bool = False

    def get_service(self, name: str) -> Optional[ServiceConfig]:
        """Get service by name.

        Args:
            name: Service name to find

        Returns:
            ServiceConfig if found, None otherwise
        """
        for service in self.services:
            if service.name == name:
                return service
        return None

    def get_services_for_scopes(self, scopes: List[str]) -> List[ServiceConfig]:
        """Map commit scopes to service configurations.

        Args:
            scopes: List of scope names from commit message

        Returns:
            List of matching ServiceConfig objects (deduplicated)
        """
        matched = []
        seen_names = set()

        for scope in scopes:
            if scope in seen_names:
                continue
            if service := self.get_service(scope):
                matched.append(service)
                seen_names.add(scope)

        return matched

    @classmethod
    def from_dict(cls, data: Dict) -> "MonorepoConfig":
        """Create MonorepoConfig from dictionary.

        Args:
            data: Dictionary with monorepo configuration

        Returns:
            MonorepoConfig instance
        """
        services = [ServiceConfig.from_dict(s) for s in data.get("services", [])]

        return cls(
            services=services,
            default_service=data.get("default_service"),
            require_scope=data.get("require_scope", False),
        )


def is_monorepo_mode(config: Dict) -> bool:
    """Check if configuration is in monorepo mode.

    Args:
        config: Pezin configuration dictionary

    Returns:
        True if mode is "monorepo", False otherwise
    """
    return config.get("mode") == "monorepo"
