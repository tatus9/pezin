"""File handlers for different version file formats."""

import json
import re
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import tomli
import tomli_w

from .version import Version


class FileHandler(ABC):
    """Abstract base class for version file handlers."""

    def __init__(self, file_path: Union[str, Path]):
        self.file_path = Path(file_path)

    @abstractmethod
    def read_version(self) -> Optional[Version]:
        """Read version from the file."""
        raise NotImplementedError()

    @abstractmethod
    def write_version(self, version: Version) -> None:
        """Write version to the file."""
        raise NotImplementedError()

    @abstractmethod
    def supports_file(self, file_path: Union[str, Path]) -> bool:
        """Check if this handler supports the given file."""
        raise NotImplementedError()


class TomlFileHandler(FileHandler):
    """Handler for TOML files (pyproject.toml, etc.)."""

    def __init__(
        self, file_path: Union[str, Path], version_keys: Optional[List[str]] = None
    ):
        super().__init__(file_path)
        self.version_keys = version_keys or [
            "project.version",
            "pezin.version",
            "tool.pezin.version",
        ]
        self._found_key = None

    def read_version(self) -> Optional[Version]:
        """Read version from TOML file."""
        if not self.file_path.exists():
            return None

        try:
            with open(self.file_path, "rb") as f:
                data = tomli.load(f)

            for key in self.version_keys:
                try:
                    if version_str := self._get_nested_value(data, key):
                        self._found_key = key
                        return Version(version_str)
                except (KeyError, TypeError):
                    continue

            return None

        except (tomli.TOMLDecodeError, OSError):
            return None

    def write_version(self, version: Version) -> None:
        """Write version to TOML file."""
        if not self.file_path.exists():
            raise FileNotFoundError(f"File not found: {self.file_path}")

        try:
            with open(self.file_path, "rb") as f:
                data = tomli.load(f)
        except (tomli.TOMLDecodeError, OSError) as e:
            raise ValueError(f"Could not read TOML file {self.file_path}: {e}") from e

        # Use the key where we found the version, or the first key as fallback
        key_to_use = self._found_key or self.version_keys[0]

        try:
            self._set_nested_value(data, key_to_use, str(version))
        except (KeyError, TypeError) as e:
            raise ValueError(
                f"Could not set version key '{key_to_use}' in {self.file_path}: {e}"
            ) from e

        try:
            with open(self.file_path, "wb") as f:
                tomli_w.dump(data, f)
        except OSError as e:
            raise ValueError(f"Could not write to file {self.file_path}: {e}") from e

    def supports_file(self, file_path: Union[str, Path]) -> bool:
        """Check if this handler supports the given file."""
        path = Path(file_path)
        return path.suffix in {".toml"} or path.name in {"pyproject.toml", "Pipfile"}

    def _get_nested_value(self, data: Dict[str, Any], key: str) -> Any:
        """Get nested value from dictionary using dot notation."""
        keys = key.split(".")
        current = data
        for k in keys:
            current = current[k]
        return current

    def _set_nested_value(self, data: Dict[str, Any], key: str, value: Any) -> None:
        """Set nested value in dictionary using dot notation."""
        keys = key.split(".")
        current = data
        for k in keys[:-1]:
            if k not in current:
                current[k] = {}
            current = current[k]
        current[keys[-1]] = value


class JsonFileHandler(FileHandler):
    """Handler for JSON files (package.json, etc.)."""

    def __init__(self, file_path: Union[str, Path], version_key: str = "version"):
        super().__init__(file_path)
        self.version_key = version_key

    def read_version(self) -> Optional[Version]:
        """Read version from JSON file."""
        if not self.file_path.exists():
            return None

        try:
            with open(self.file_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            if version_str := self._get_nested_value(data, self.version_key):
                return Version(version_str)

            return None

        except (json.JSONDecodeError, OSError, KeyError, TypeError):
            return None

    def write_version(self, version: Version) -> None:
        """Write version to JSON file."""
        if not self.file_path.exists():
            raise FileNotFoundError(f"File not found: {self.file_path}")

        try:
            with open(self.file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            raise ValueError(f"Could not read JSON file {self.file_path}: {e}") from e

        try:
            self._set_nested_value(data, self.version_key, str(version))
        except (KeyError, TypeError) as e:
            raise ValueError(
                f"Could not set version key '{self.version_key}' in {self.file_path}: {e}"
            ) from e

        try:
            with open(self.file_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except OSError as e:
            raise ValueError(f"Could not write to file {self.file_path}: {e}") from e

    def supports_file(self, file_path: Union[str, Path]) -> bool:
        """Check if this handler supports the given file."""
        path = Path(file_path)
        return path.suffix == ".json" or path.name in {"package.json", "composer.json"}

    def _get_nested_value(self, data: Dict[str, Any], key: str) -> Any:
        """Get nested value from dictionary using dot notation."""
        keys = key.split(".")
        current = data
        for k in keys:
            current = current[k]
        return current

    def _set_nested_value(self, data: Dict[str, Any], key: str, value: Any) -> None:
        """Set nested value in dictionary using dot notation."""
        keys = key.split(".")
        current = data
        for k in keys[:-1]:
            if k not in current:
                current[k] = {}
            current = current[k]
        current[keys[-1]] = value


class GenericFileHandler(FileHandler):
    """Handler for generic text files using regex patterns."""

    def __init__(
        self,
        file_path: Union[str, Path],
        version_pattern: Optional[str] = None,
        version_replacement: Optional[str] = None,
        version_format: Optional[str] = None,
        encoding: str = "utf-8",
    ):
        super().__init__(file_path)
        # Use a simple default pattern if none provided
        self.version_pattern = version_pattern or r'version["\s]*[=:]["\s]*([^\s"\']+)'
        self.version_replacement = version_replacement or r'version = "{version}"'
        self.version_format = version_format  # New: template for output formatting
        self.encoding = encoding
        self._compiled_pattern = re.compile(self.version_pattern, re.MULTILINE)

    def read_version(self) -> Optional[Version]:
        """Read version from generic text file using regex.

        Supports both single-group patterns (full version string) and
        multi-group patterns (major, minor, patch components).
        """
        if not self.file_path.exists():
            return None

        try:
            with open(self.file_path, "r", encoding=self.encoding) as f:
                content = f.read()

            if match := self._compiled_pattern.search(content):
                groups = match.groups()

                if len(groups) >= 3:
                    # Check if this looks like component parsing (all groups are digits)
                    try:
                        # Try to parse first 3 groups as numeric components
                        int(groups[0])  # major
                        int(groups[1])  # minor
                        int(groups[2])  # patch
                        # If we get here, it's a valid component pattern
                        return Version.parse_components(groups, self.version_format)
                    except ValueError:
                        # Not a component pattern, treat as prefix/version/suffix pattern
                        # Look for the version string in the middle group(s)
                        for group in groups:
                            # Skip groups that look like prefixes or suffixes
                            if group and all(
                                char not in group for char in ['"', "'", "#", "=", ":"]
                            ):
                                try:
                                    return Version(
                                        group, original_format=self.version_format
                                    )
                                except Exception:
                                    continue
                        # Fallback to second group (common pattern: prefix, version, suffix)
                        if len(groups) >= 2:
                            return Version(
                                groups[1], original_format=self.version_format
                            )
                        else:
                            return Version(
                                groups[0], original_format=self.version_format
                            )
                else:
                    # Single or double group pattern: full version string
                    version_str = groups[1] if len(groups) >= 2 else groups[0]
                    return Version(version_str, original_format=self.version_format)

            return None

        except (OSError, re.error):
            return None

    def write_version(self, version: Version) -> None:
        """Write version to generic text file using regex replacement."""
        if not self.file_path.exists():
            raise FileNotFoundError(f"File not found: {self.file_path}")

        try:
            with open(self.file_path, "r", encoding=self.encoding) as f:
                content = f.read()
        except (OSError, UnicodeDecodeError) as e:
            raise ValueError(f"Could not read file {self.file_path}: {e}") from e

        try:
            # Use template-based replacement with all version components available
            replacement_text = version.format_with_template(self.version_replacement)
            new_content = self._compiled_pattern.sub(replacement_text, content)
        except re.error as e:
            raise ValueError(
                f"Regex replacement failed for {self.file_path}: {e}"
            ) from e

        if new_content == content:
            raise ValueError(f"No version pattern found in {self.file_path}")

        try:
            with open(self.file_path, "w", encoding=self.encoding) as f:
                f.write(new_content)
        except (OSError, UnicodeEncodeError) as e:
            raise ValueError(f"Could not write to file {self.file_path}: {e}") from e

    def supports_file(self, file_path: Union[str, Path]) -> bool:
        """Check if this handler supports the given file."""
        # Generic handler can support any file, but should be used as fallback
        return True


class FileHandlerFactory:
    """Factory for creating appropriate file handlers."""

    @staticmethod
    def create_handler(
        file_path: Union[str, Path], file_type: Optional[str] = None, **kwargs
    ) -> FileHandler:
        """Create appropriate handler for the given file."""
        path = Path(file_path)

        if file_type:
            # Explicit file type specified
            if file_type.lower() == "toml":
                return TomlFileHandler(file_path, **kwargs)
            elif file_type.lower() == "json":
                return JsonFileHandler(file_path, **kwargs)
            elif file_type.lower() == "generic":
                return GenericFileHandler(file_path, **kwargs)
            else:
                # Unknown file type, fallback to generic
                return GenericFileHandler(file_path, **kwargs)

        # Auto-detect based on file extension/name
        if path.suffix in {".toml"} or path.name in {"pyproject.toml", "Pipfile"}:
            return TomlFileHandler(file_path, **kwargs)
        elif path.suffix == ".json" or path.name in {
            "package.json",
            "composer.json",
        }:
            return JsonFileHandler(file_path, **kwargs)
        else:
            # Fallback to generic handler
            return GenericFileHandler(file_path, **kwargs)

    @staticmethod
    def get_supported_handlers() -> List[str]:
        """Get list of supported handler types."""
        return ["toml", "json", "generic"]


# Common patterns for different file types
COMMON_PATTERNS = {
    "c_header": {
        "pattern": r'(#define\s+VERSION\s+["\']?)([^"\']+)(["\']?)',
        "replacement": r"\g<1>{version}\g<3>",
    },
    "cmake": {"pattern": r"(VERSION\s+)([^\s)]+)", "replacement": r"\g<1>{version}"},
    "dockerfile": {
        "pattern": r'(LABEL\s+version\s*=\s*["\']?)([^"\']+)(["\']?)',
        "replacement": r"\g<1>{version}\g<3>",
    },
    "makefile": {
        "pattern": r"(VERSION\s*[:=]\s*)([^\s]+)",
        "replacement": r"\g<1>{version}",
    },
    "shell_script": {
        "pattern": r'(VERSION\s*=\s*["\']?)([^"\']+)(["\']?)',
        "replacement": r"\g<1>{version}\g<3>",
    },
}
