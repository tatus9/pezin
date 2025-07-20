# Multi-Language Version Management Examples

This document demonstrates how to configure Pezin for different programming languages and project types.

## Example 1: Python Project (Zero-Config)

```toml
# pyproject.toml (automatically detected)
[project]
name = "my-python-project"
version = "1.0.0"
```

*No additional configuration needed! Pezin automatically detects and updates pyproject.toml*

## Example 2: Node.js Project (Zero-Config)

```json
# package.json (automatically detected)
{
  "name": "my-node-project",
  "version": "1.0.0"
}
```

*No additional configuration needed! Pezin automatically detects and updates package.json*

## Example 3: Full-Stack Project (Python + Node.js)

```toml
# pyproject.toml (Python project root)
[project]
name = "fullstack-app"
version = "1.0.0"

[tool.pezin]
version_files = [
    # Python backend (auto-detected)
    {path = "pyproject.toml"},
<<<<<<< HEAD

    # Node.js frontend
    {path = "frontend/package.json", file_type = "json"},

=======

    # Node.js frontend
    {path = "frontend/package.json", file_type = "json"},

>>>>>>> 66fcc00 (docs: restructure README and create comprehensive documentation)
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
# pezin.toml (project root)
[pezin]
version_files = [
    # Version header
    {
        path = "include/version.h",
        file_type = "generic",
        version_pattern = '#define VERSION "([^"]+)"',
        version_replacement = '#define VERSION "{version}"'
    },
<<<<<<< HEAD

=======

>>>>>>> 66fcc00 (docs: restructure README and create comprehensive documentation)
    # CMake project version
    {
        path = "CMakeLists.txt",
        file_type = "generic",
        version_pattern = "(project\\([^)]+VERSION\\s+)([^\\s)]+)",
        version_replacement = "\\g<1>{version}"
    },
<<<<<<< HEAD

=======

>>>>>>> 66fcc00 (docs: restructure README and create comprehensive documentation)
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
# pezin.toml (project root)
[pezin]
version_files = [
    # Go version constant
    {
        path = "version.go",
        file_type = "generic",
        version_pattern = 'const Version = "([^"]+)"',
        version_replacement = 'const Version = "{version}"'
    },
<<<<<<< HEAD

=======

>>>>>>> 66fcc00 (docs: restructure README and create comprehensive documentation)
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
# pezin.toml (project root)
[pezin]
version_files = [
    # Maven POM version
    {
        path = "pom.xml",
        file_type = "generic",
        version_pattern = "<version>([^<]+)</version>",
        version_replacement = "<version>{version}</version>"
    },
<<<<<<< HEAD

=======

>>>>>>> 66fcc00 (docs: restructure README and create comprehensive documentation)
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
[tool.pezin]
version_files = [
    # Main Cargo.toml (auto-detected)
    {path = "Cargo.toml"},
<<<<<<< HEAD

=======

>>>>>>> 66fcc00 (docs: restructure README and create comprehensive documentation)
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

If you need additional version files, create `pezin.toml`:

```toml
# pezin.toml (if additional files needed)
[pezin]
version_files = [
    # Main composer.json (auto-detected)
    {path = "composer.json", file_type = "json"},
<<<<<<< HEAD

=======

>>>>>>> 66fcc00 (docs: restructure README and create comprehensive documentation)
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
# pezin.toml (project root)
[pezin]
version_files = [
    # Node.js services (auto-detected)
    { path = "services/api/package.json", file_type = "json" },
    { path = "services/worker/package.json", file_type = "json" },
<<<<<<< HEAD

    # Rust libraries (auto-detected)
    { path = "libs/core/Cargo.toml", file_type = "toml" },

    # Go microservice
    {
        path = "services/gateway/version.go",
=======

    # Rust libraries (auto-detected)
    { path = "libs/core/Cargo.toml", file_type = "toml" },

    # Go microservice
    {
        path = "services/gateway/version.go",
>>>>>>> 66fcc00 (docs: restructure README and create comprehensive documentation)
        file_type = "generic",
        version_pattern = 'const Version = "([^"]+)"',
        version_replacement = 'const Version = "{version}"'
    },
<<<<<<< HEAD

=======

>>>>>>> 66fcc00 (docs: restructure README and create comprehensive documentation)
    # C++ library
    {
        path = "libs/native/version.h",
        file_type = "generic",
        version_pattern = '#define VERSION "([^"]+)"',
        version_replacement = '#define VERSION "{version}"'
    },
<<<<<<< HEAD

    # Python service
    { path = "services/analytics/pyproject.toml", file_type = "toml" },

    # Deployment files
    {
        path = "k8s/deployment.yaml",
        file_type = "generic",
=======

    # Python service
    { path = "services/analytics/pyproject.toml", file_type = "toml" },

    # Deployment files
    {
        path = "k8s/deployment.yaml",
        file_type = "generic",
>>>>>>> 66fcc00 (docs: restructure README and create comprehensive documentation)
        version_pattern = '(image: myapp:)([^\\s]+)',
        version_replacement = '\\g<1>{version}'
    }
]

[pezin.changelog]
enabled = true
file_path = "CHANGELOG.md"
```

## Pre-commit Hook Setup

After configuring your version files, update your `.pre-commit-config.yaml`:

### For Zero-Config Projects (Python, Node.js, Rust, PHP)

```yaml
repos:
<<<<<<< HEAD
  - repo: https://github.com/tatus9/pezin
=======
  - repo: https://github.com/tatus9/pezin
>>>>>>> 66fcc00 (docs: restructure README and create comprehensive documentation)
    rev: v1.1.0  # Use the latest version
    hooks:
      - id: pezin
```

### For Custom Config Projects (C/C++, Go, Java, etc.)

```yaml
repos:
  - repo: local
    hooks:
      - id: pezin
        name: Pezin Version Control
        entry: python3 -m pezin.hooks.pre_commit
        language: system
        stages: [commit-msg]
        always_run: true
        pass_filenames: false
        args: ["--config", "pezin.toml"]
```

## Usage Examples

Once configured, Pezin will automatically update all specified files when you make commits with conventional commit messages:

```bash
# Zero-config project (Python/Node.js/Rust/PHP)
git commit -m "feat: add new authentication feature"
# Automatically bumps minor version in project file

# Custom config project (C/C++/Go/Java)
<<<<<<< HEAD
git commit -m "fix: resolve memory leak in parser"
=======
git commit -m "fix: resolve memory leak in parser"
>>>>>>> 66fcc00 (docs: restructure README and create comprehensive documentation)
# Automatically bumps patch version in all configured files

# Multi-language project
git commit -m "feat!: redesign API interface"
# Automatically bumps major version across all configured files
```

## Manual Version Bumping

You can also manually bump versions using the CLI:

```bash
# Bump minor version across all files
pezin bump minor

# Bump patch version with pre-release label
pezin bump patch --prerelease alpha

# Dry run to see what would change
pezin bump major --dry-run

# Use specific config file
pezin bump minor --config pezin.toml
```

## Configuration Guidelines

### When to Use Each Approach

1. **Zero-Config (Recommended)**: For Python, Node.js, Rust, or PHP projects with standard project files
2. **Python Multi-File**: When Python is the main project but you need to update other files
3. **Custom Config**: For C/C++, Go, Java, or any language without standard version files
4. **Monorepo**: When managing multiple languages/services in one repository

### Tips

1. **Version Consistency**: Pezin validates that all files have the same version before bumping
2. **Regex Testing**: Test your regex patterns with online tools before configuring
3. **File Encoding**: Specify encoding if your files use non-UTF-8 encoding
4. **Backup**: Always test your configuration with `--dry-run` first
<<<<<<< HEAD
5. **Git Staging**: Pezin automatically stages updated files for you
=======
5. **Git Staging**: Pezin automatically stages updated files for you
>>>>>>> 66fcc00 (docs: restructure README and create comprehensive documentation)
