# Advanced Pattern System

Pezin supports sophisticated version patterns with component-level control and template-based formatting.

## Custom Version Formats

Control how versions are formatted using the `version_format` parameter with `{major}`, `{minor}`, and `{patch}` placeholders:

```toml
[[pezin.version_files]]
path = "version.txt"
file_type = "generic"
version_pattern = 'Version: ([^\\s]+)'
version_replacement = 'Version: {formatted_version}'
version_format = "v{major}.{minor}.{patch}"  # Custom format

# Examples of version_format patterns:
# "v{major}.{minor}.{patch}"           → v1.2.3
# "{major}.{minor}.{patch}v"           → 1.2.3v
# "release-{major}.{minor}.{patch}"    → release-1.2.3
# "{major}.{minor}.{patch}-stable"     → 1.2.3-stable
```

This allows any project to use custom version formats while maintaining semantic versioning underneath.

## Multi-Component Patterns

Extract major, minor, and patch versions separately for ultimate flexibility:

```toml
# C/C++ with separate version components
[[pezin.version_files]]
path = "src/version.h"
file_type = "generic"
version_pattern = '#define VERSION_MAJOR (\d+)\s*\n#define VERSION_MINOR (\d+)\s*\n#define VERSION_PATCH (\d+)'
version_replacement = '''#define VERSION_MAJOR {major}
#define VERSION_MINOR {minor}
#define VERSION_PATCH {patch}
#define VERSION_STRING "v{major}.{minor}.{patch}"
#define BUILD_DATE "{date}"'''
version_format = "v{major}.{minor}.{patch}"

# Android Gradle properties
[[pezin.version_files]]
path = "gradle.properties"
file_type = "generic"
version_pattern = 'versionMajor=(\d+)\s*\nversionMinor=(\d+)\s*\nversionPatch=(\d+)'
version_replacement = '''versionMajor={major}
versionMinor={minor}
versionPatch={patch}
# Auto-generated: {major}.{minor}.{patch} built on {date}'''

# .NET AssemblyInfo with 4-component versioning
[[pezin.version_files]]
path = "Properties/AssemblyInfo.cs"
file_type = "generic"
version_pattern = '\[assembly: AssemblyVersion\("(\d+)\.(\d+)\.(\d+)"'
version_replacement = '[assembly: AssemblyVersion("{major}.{minor}.{patch}.0")]'
```

## Template Variables

Rich set of template variables for flexible version formatting:

### Version Components
- `{version}` - Full semantic version (1.2.3)
- `{major}`, `{minor}`, `{patch}` - Individual version numbers
- `{major_padded}`, `{minor_padded}`, `{patch_padded}` - Zero-padded (001.002.003)
- `{prerelease}` - Pre-release label (alpha, beta, rc)
- `{build}` - Build metadata

### Date/Build Information
- `{date}` - Current date (YYYY-MM-DD)
- `{year}`, `{month}`, `{day}` - Date components
- `{timestamp}` - Unix timestamp

## Real-World Examples

### Go Module with Multiple Formats
```toml
[[pezin.version_files]]
path = "version.go"
file_type = "generic"
version_pattern = 'const Major = (\d+)\s*\nconst Minor = (\d+)\s*\nconst Patch = (\d+)'
version_replacement = '''const Major = {major}
const Minor = {minor}
const Patch = {patch}
const Version = "{major}.{minor}.{patch}"
const VersionWithPrefix = "v{major}.{minor}.{patch}"
const BuildInfo = "Built on {date} ({timestamp})"'''
```

### CMake Project with Documentation
```toml
[[pezin.version_files]]
path = "CMakeLists.txt"
file_type = "generic"
version_pattern = 'set\(VERSION_MAJOR (\d+)\)\s*\nset\(VERSION_MINOR (\d+)\)\s*\nset\(VERSION_PATCH (\d+)\)'
version_replacement = '''set(VERSION_MAJOR {major})
set(VERSION_MINOR {minor})
set(VERSION_PATCH {patch})
# Project version: {major}.{minor}.{patch} ({date})'''
```

### Docker Multi-Stage with Build Info
```toml
[[pezin.version_files]]
path = "Dockerfile"
file_type = "generic"
version_pattern = 'ARG VERSION=([^\s]+)'
version_replacement = '''ARG VERSION={major}.{minor}.{patch}
LABEL version="{major}.{minor}.{patch}"
LABEL build-date="{date}"
LABEL build-timestamp="{timestamp}"'''
```

For complete multi-language examples, see [`examples/multi-language-setup.md`](../examples/multi-language-setup.md).
