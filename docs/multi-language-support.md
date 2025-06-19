# Multi-Language Support

Pumper supports version management for any programming language through a flexible file handler system. It can update version information in various file formats regardless of the programming language used.

## File Handler Types

Pumper uses three types of file handlers to update version information:

### 1. TOML Files (`TomlFileHandler`)
- Handles `.toml` configuration files
- Supports nested keys like `project.version`, `package.version`
- Examples: `pyproject.toml`, `Cargo.toml`

### 2. JSON Files (`JsonFileHandler`)
- Handles `.json` configuration files
- Supports nested version fields
- Examples: `package.json`, `composer.json`

### 3. Generic Text Files (`GenericFileHandler`)
- Handles any text file using regex patterns
- Completely customizable version patterns
- Examples: Header files, Makefiles, scripts, config files

## Zero-Config Languages

These languages have standardized project files that Pumper automatically detects:

### Python Projects
```toml
# pyproject.toml (automatically detected)
[project]
name = "my-python-project"
version = "1.0.0"
```

### Node.js Projects
```json
# package.json (automatically detected)
{
  "name": "my-node-project",
  "version": "1.0.0"
}
```

### Rust Projects
```toml
# Cargo.toml (automatically detected)
[package]
name = "my-rust-project"
version = "1.0.0"
```

### PHP Projects
```json
# composer.json (automatically detected)
{
    "name": "my/php-project",
    "version": "1.0.0"
}
```

## Custom Configuration Languages

For languages without standardized version files, use `pumper.toml` configuration:

### C/C++, Go, Java, and Other Languages

Create a `pumper.toml` file in your project root:

```toml
[pumper]
version_files = [
    # C/C++ header file
    {
        path = "src/version.h",
        file_type = "generic",
        version_pattern = '#define VERSION "([^"]+)"',
        version_replacement = '#define VERSION "{version}"'
    },

    # Go version constant
    {
        path = "version.go",
        file_type = "generic",
        version_pattern = 'const Version = "([^"]+)"',
        version_replacement = 'const Version = "{version}"'
    },

    # Java version constant
    {
        path = "src/main/java/com/example/Version.java",
        file_type = "generic",
        version_pattern = 'public static final String VERSION = "([^"]+)";',
        version_replacement = 'public static final String VERSION = "{version}";'
    },

    # CMake project file
    {
        path = "CMakeLists.txt",
        file_type = "generic",
        version_pattern = '(project\\([^)]+VERSION\\s+)([^\\s)]+)',
        version_replacement = '\\g<1>{version}'
    },

    # Makefile
    {
        path = "Makefile",
        file_type = "generic",
        version_pattern = '(VERSION\\s*[:=]\\s*)([^\\s]+)',
        version_replacement = '\\g<1>{version}'
    },

    # Maven POM (Java)
    {
        path = "pom.xml",
        file_type = "generic",
        version_pattern = '<version>([^<]+)</version>',
        version_replacement = '<version>{version}</version>'
    }
]

# Optional: Changelog configuration
[pumper.changelog]
enabled = true
file_path = "CHANGELOG.md"
```

## Multi-Language Project Examples

### Python + Node.js + Docker

For projects mixing different languages, configure from the main project file:

```toml
# pyproject.toml (Python project root)
[project]
name = "fullstack-app"
version = "1.0.0"

[tool.pumper]
version_files = [
    # Python backend (auto-detected)
    { path = "pyproject.toml" },

    # Node.js frontend
    { path = "frontend/package.json", file_type = "json" },

    # Docker deployment
    {
        path = "Dockerfile",
        file_type = "generic",
        version_pattern = '(LABEL version=")([^"]+)(")',
        version_replacement = '\\g<1>{version}\\g<3>'
    }
]
```

### Monorepo with Multiple Languages

```toml
# pumper.toml (project root)
[pumper]
version_files = [
    # Node.js services
    { path = "services/api/package.json", file_type = "json" },
    { path = "services/worker/package.json", file_type = "json" },

    # Rust libraries
    { path = "libs/core/Cargo.toml", file_type = "toml" },

    # Go microservice
    {
        path = "services/gateway/version.go",
        file_type = "generic",
        version_pattern = 'const Version = "([^"]+)"',
        version_replacement = 'const Version = "{version}"'
    },

    # C++ library
    {
        path = "libs/native/version.h",
        file_type = "generic",
        version_pattern = '#define VERSION "([^"]+)"',
        version_replacement = '#define VERSION "{version}"'
    },

    # Deployment files
    {
        path = "k8s/deployment.yaml",
        file_type = "generic",
        version_pattern = '(image: myapp:)([^\\s]+)',
        version_replacement = '\\g<1>{version}'
    }
]

[pumper.changelog]
enabled = true
file_path = "CHANGELOG.md"
```

## Configuration Priority

Pumper searches for configuration in this order:
1. `--config` CLI argument (if provided)
2. `pumper.toml` in current directory
3. `[tool.pumper]` section in `pyproject.toml` (Python projects)
4. `[pumper]` section in `pyproject.toml` (legacy)

## Common Patterns by Language/Tool

Ready-to-use patterns for popular languages and build systems:

| Language/Tool | Pattern | Replacement | Example |
|--------------|---------|-------------|---------|
| **C/C++ Header** | `'#define VERSION "([^"]+)"'` | `'#define VERSION "{version}"'` | `#define VERSION "1.0.0"` |
| **CMake** | `'(project\\([^)]+VERSION\\s+)([^\\s)]+)'` | `'\\g<1>{version}'` | `project(MyApp VERSION 1.0.0)` |
| **Go** | `'const Version = "([^"]+)"'` | `'const Version = "{version}"'` | `const Version = "1.0.0"` |
| **Java Maven** | `'<version>([^<]+)</version>'` | `'<version>{version}</version>'` | `<version>1.0.0</version>` |
| **Shell Script** | `'(VERSION=")([^"]+)(")'` | `'\\g<1>{version}\\g<3>'` | `VERSION="1.0.0"` |
| **Makefile** | `'(VERSION\\s*[:=]\\s*)([^\\s]+)'` | `'\\g<1>{version}'` | `VERSION = 1.0.0` |
| **Docker** | `'(LABEL version=")([^"]+)(")'` | `'\\g<1>{version}\\g<3>'` | `LABEL version="1.0.0"` |
| **Gradle** | `'(version\\s*=\\s*["\'])([^"\']+)(["\'])'` | `'\\g<1>{version}\\g<3>'` | `version = "1.0.0"` |
