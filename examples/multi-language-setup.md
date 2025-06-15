# Multi-Language Version Management Examples

This document demonstrates how to configure Pumper for different programming languages and project types.

## Example 1: Python Project (Zero-Config)

```toml
# pyproject.toml (automatically detected)
[project]
name = "my-python-project"
version = "1.0.0"
```

*No additional configuration needed! Pumper automatically detects and updates pyproject.toml*

## Example 2: Node.js Project (Zero-Config)

```json
# package.json (automatically detected)
{
  "name": "my-node-project",
  "version": "1.0.0"
}
```

*No additional configuration needed! Pumper automatically detects and updates package.json*

## Example 3: Full-Stack Project (Python + Node.js)

```toml
# pyproject.toml (Python project root)
[project]
name = "fullstack-app"
version = "1.0.0"

[tool.pumper]
version_files = [
    # Python backend (auto-detected)
    {path = "pyproject.toml"},

    # Node.js frontend
    {path = "frontend/package.json", file_type = "json"},

    # Docker image
    {
        path = "Dockerfile",
        file_type = "generic",
        version_pattern = 'LABEL version="([^"]+)"',
        version_replacement = 'LABEL version="{version}"'
    }
]
```

## Example 4: C/C++ Project

```toml
# pumper.toml (project root)
[pumper]
version_files = [
    # Version header
    {
        path = "include/version.h",
        file_type = "generic",
        version_pattern = '#define VERSION "([^"]+)"',
        version_replacement = '#define VERSION "{version}"'
    },

    # CMake project version
    {
        path = "CMakeLists.txt",
        file_type = "generic",
        version_pattern = "(project\\([^)]+VERSION\\s+)([^\\s)]+)",
        version_replacement = "\\g<1>{version}"
    },

    # Makefile version
    {
        path = "Makefile",
        file_type = "generic",
        version_pattern = "(VERSION\\s*=\\s*)([^\\s]+)",
        version_replacement = "\\g<1>{version}"
    }
]
```

## Example 5: Go Project

```toml
# pumper.toml (project root)
[pumper]
version_files = [
    # Go version constant
    {
        path = "version.go",
        file_type = "generic",
        version_pattern = 'const Version = "([^"]+)"',
        version_replacement = 'const Version = "{version}"'
    },

    # Dockerfile for containerized Go app
    {
        path = "Dockerfile",
        file_type = "generic",
        version_pattern = 'ARG VERSION=([^\\s]+)',
        version_replacement = 'ARG VERSION={version}'
    }
]
```

## Example 6: Java Maven Project

```toml
# pumper.toml (project root)
[pumper]
version_files = [
    # Maven POM version
    {
        path = "pom.xml",
        file_type = "generic",
        version_pattern = "<version>([^<]+)</version>",
        version_replacement = "<version>{version}</version>"
    },

    # Java version constant
    {
        path = "src/main/java/com/example/Version.java",
        file_type = "generic",
        version_pattern = 'public static final String VERSION = "([^"]+)";',
        version_replacement = 'public static final String VERSION = "{version}";'
    }
]
```

## Example 7: Rust Project (Zero-Config + Custom)

```toml
# Cargo.toml (automatically detected)
[package]
name = "my-rust-project"
version = "1.0.0"

# If you need additional version files
[tool.pumper]
version_files = [
    # Main Cargo.toml (auto-detected)
    {path = "Cargo.toml"},

    # Version constant in source
    {
        path = "src/version.rs",
        file_type = "generic",
        version_pattern = 'pub const VERSION: &str = "([^"]+)";',
        version_replacement = 'pub const VERSION: &str = "{version}";'
    }
]
```

## Example 8: PHP Project (Zero-Config + Custom)

```json
# composer.json (automatically detected)
{
    "name": "my/php-project",
    "version": "1.0.0"
}
```

If you need additional version files, create `pumper.toml`:

```toml
# pumper.toml (if additional files needed)
[pumper]
version_files = [
    # Main composer.json (auto-detected)
    {path = "composer.json", file_type = "json"},

    # PHP version constant
    {
        path = "src/Version.php",
        file_type = "generic",
        version_pattern = "const VERSION = '([^']+)';",
        version_replacement = "const VERSION = '{version}';"
    }
]
```

## Example 9: Monorepo with Multiple Languages

```toml
# pumper.toml (project root)
[pumper]
version_files = [
    # Node.js services (auto-detected)
    { path = "services/api/package.json", file_type = "json" },
    { path = "services/worker/package.json", file_type = "json" },

    # Rust libraries (auto-detected)
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

    # Python service
    { path = "services/analytics/pyproject.toml", file_type = "toml" },

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

## Pre-commit Hook Setup

After configuring your version files, update your `.pre-commit-config.yaml`:

### For Zero-Config Projects (Python, Node.js, Rust, PHP)

```yaml
repos:
  - repo: https://github.com/tatus9/pumper
    rev: v1.1.0  # Use the latest version
    hooks:
      - id: pumper
```

### For Custom Config Projects (C/C++, Go, Java, etc.)

```yaml
repos:
  - repo: local
    hooks:
      - id: pumper
        name: Pumper Version Control
        entry: python3 -m pumper.hooks.pre_commit
        language: system
        stages: [commit-msg]
        always_run: true
        pass_filenames: false
        args: ["--config", "pumper.toml"]
```

## Usage Examples

Once configured, Pumper will automatically update all specified files when you make commits with conventional commit messages:

```bash
# Zero-config project (Python/Node.js/Rust/PHP)
git commit -m "feat: add new authentication feature"
# Automatically bumps minor version in project file

# Custom config project (C/C++/Go/Java)
git commit -m "fix: resolve memory leak in parser"
# Automatically bumps patch version in all configured files

# Multi-language project
git commit -m "feat!: redesign API interface"
# Automatically bumps major version across all configured files
```

## Manual Version Bumping

You can also manually bump versions using the CLI:

```bash
# Bump minor version across all files
pumper bump minor

# Bump patch version with pre-release label
pumper bump patch --prerelease alpha

# Dry run to see what would change
pumper bump major --dry-run

# Use specific config file
pumper bump minor --config pumper.toml
```

## Configuration Guidelines

### When to Use Each Approach

1. **Zero-Config (Recommended)**: For Python, Node.js, Rust, or PHP projects with standard project files
2. **Python Multi-File**: When Python is the main project but you need to update other files
3. **Custom Config**: For C/C++, Go, Java, or any language without standard version files
4. **Monorepo**: When managing multiple languages/services in one repository

### Tips

1. **Version Consistency**: Pumper validates that all files have the same version before bumping
2. **Regex Testing**: Test your regex patterns with online tools before configuring
3. **File Encoding**: Specify encoding if your files use non-UTF-8 encoding
4. **Backup**: Always test your configuration with `--dry-run` first
5. **Git Staging**: Pumper automatically stages updated files for you
