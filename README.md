# 🌱 Pezin

[![CI](https://github.com/tatus9/pezin/workflows/CI/badge.svg)](https://github.com/tatus9/pezin/actions/workflows/ci.yml)
[![PyPI version](https://img.shields.io/pypi/v/pezin.svg)](https://pypi.org/project/pezin/)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://pypi.org/project/pezin/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Downloads](https://img.shields.io/pypi/dm/pezin.svg)](https://pypi.org/project/pezin/)

A tool that handles versioning with care — it can be used manually or integrated as a pre-commit hook to automate version bumps and changelog generation based on conventional commits.

## Features

- 🔄 **Automatic version bumping** based on conventional commits
- 🌍 **Universal language support** - Python, Node.js, C/C++, Rust, PHP, Go, Java, .NET, and any custom patterns
- 📁 **Multi-file version management** - Update multiple version files simultaneously
- 🎨 **Advanced pattern system** - Component-level version control with rich template formatting
- 📝 **Automated changelog generation** with comparison links
- 🎣 **Git pre-commit hook integration** with reliable amend detection
- ⚡ **CLI tool** for manual version management
- 🏷️ **Pre-release version support** (alpha, beta, rc)
- 🔧 **Flexible version formats** - Support any prefix/suffix pattern (v1.2.3, 1.2.3v, release-1.2.3)

## Quick Start

### Installation

Install from PyPI:

```bash
pip install pezin
```

Or install the latest development version:

```bash
pip install git+https://github.com/tatus9/pezin.git
```

### Setup Git Hook

Add to your `.pre-commit-config.yaml`:

```yaml
repos:
  - repo: https://github.com/tatus9/pezin
    rev: v0.1.2  # Use the latest version
    hooks:
      - id: pezin
```

Install the hooks:

```bash
pip install pre-commit pezin
pre-commit install --hook-type commit-msg
```

### Start Using

Just commit with conventional commit format:

```bash
git commit -m "feat: add user authentication"    # 1.0.0 → 1.1.0
git commit -m "fix: resolve login bug"           # 1.1.0 → 1.1.1
git commit -m "feat!: redesign API"              # 1.1.1 → 2.0.0
```

Your version files will be automatically updated!

## Conventional Commits

| Type | Version Bump | Example |
|------|--------------|---------|
| `feat:` | Minor (1.0.0 → 1.1.0) | `feat: add user dashboard` |
| `fix:` | Patch (1.0.0 → 1.0.1) | `fix: resolve login issue` |
| `feat!:` | Major (1.0.0 → 2.0.0) | `feat!: redesign API` |
| `docs:`, `chore:`, etc. | No bump | `docs: update readme` |

**Special tokens:**
- `[skip-bump]` - Skip version bump
- `[force-major]` - Force major bump
- `[pre-release=beta]` - Add pre-release label

## CLI Usage

```bash
# Check versions
pezin -v                       # Shows current project + pezin versions
pezin version                  # Same as above

# Manual version bumping
pezin minor                    # Bump minor version
pezin patch --dry-run          # Preview changes
pezin major --pre-release rc   # Pre-release version

# Custom configuration
pezin patch --config package.json
pezin minor --skip-changelog

# Multi-language project example
# Updates pyproject.toml, package.json, version.h simultaneously
git commit -m "feat: add multi-platform support"
```

## Python API

```python
from pezin import Version, ConventionalCommit, ChangelogManager

# Parse and bump version
version = Version.parse("1.2.3")
new_version = version.bump("minor")
print(str(new_version))  # "1.3.0"

# Parse commit message
commit = ConventionalCommit.parse(
    "feat(api)!: add new endpoint\n\nBREAKING CHANGE: new auth"
)
print(commit.breaking)  # True

# Update changelog
config = ChangelogConfig(repo_url="https://github.com/tatus9/pezin.git")
manager = ChangelogManager(config)
manager.update_changelog(
    Path("CHANGELOG.md"),
    str(new_version),
    [commit]
)
```

## Conventional Commits Guide

Pezin follows the [Conventional Commits](https://www.conventionalcommits.org/) specification:

### Basic Format
```
<type>[optional scope]: <description>

[optional body]

[optional footer(s)]
```

### Version Bump Rules
- `feat`: Minor version bump (1.0.0 → 1.1.0) - New features
- `fix`: Patch version bump (1.0.0 → 1.0.1) - Bug fixes
- `!` or `BREAKING CHANGE`: Major version bump (1.0.0 → 2.0.0) - Breaking changes

### Other Commit Types (no version bump)
- `docs`: Documentation changes
- `style`: Code style/formatting changes
- `refactor`: Code refactoring without functional changes
- `perf`: Performance improvements
- `test`: Adding or updating tests
- `chore`: Maintenance tasks, dependency updates
- `ci`: CI/CD configuration changes
- `build`: Build system changes

### Special Footer Tokens
Control version bumping behavior with footer tokens:

```bash
# Skip version bump entirely
git commit -m "feat: new feature

[skip-bump]"

# Force specific bump type
git commit -m "docs: update readme

[force-patch]"

# Add pre-release label
git commit -m "feat: beta feature

[pre-release=beta]"
```

Available tokens:
- `[skip-bump]`: Skip version bump
- `[force-major]`: Force major bump (1.0.0 → 2.0.0)
- `[force-minor]`: Force minor bump (1.0.0 → 1.1.0)
- `[force-patch]`: Force patch bump (1.0.0 → 1.0.1)
- `[pre-release=label]`: Add pre-release label (alpha, beta, rc)

## Documentation

- 📖 **[Quick Start Guide](docs/quick-start.md)** - Get started in minutes
- 📖 **[Installation Guide](docs/installation.md)** - Detailed setup instructions
- 🌍 **[Multi-Language Support](docs/multi-language-support.md)** - Python, Node.js, C++, Rust, and more
- 🎨 **[Advanced Patterns](docs/advanced-patterns.md)** - Custom version formats and templates
- 📋 **[Conventional Commits](docs/conventional-commits.md)** - Complete commit format guide
- ⚙️ **[Configuration](docs/configuration.md)** - Customize Pezin behavior
- 💻 **[CLI Usage](docs/cli-usage.md)** - Manual version management
- 🐍 **[Python API](docs/python-api.md)** - Programmatic usage
- 🔧 **[Troubleshooting](docs/troubleshooting.md)** - Common issues and solutions

### Examples

- 🌍 **[Multi-Language Examples](examples/multi-language-setup.md)** - Complete project setups

## Contributing

We welcome contributions!

## License

MIT License - feel free to use this project for any purpose.
