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
    rev: v0.8.2  # Use the latest version
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

## Changelog Automation

Since **v0.8.0** the post-commit hook also writes `CHANGELOG.md` on every
bump. It promotes the `[Unreleased]` section into a dated `[<version>]`
section and lists the originating commit under the matching category
(Features, Bug Fixes, …). No config required — it's on by default.

Opt out or customise via `[tool.pezin.changelog]`:

```toml
[tool.pezin.changelog]
enabled = true                  # set false to skip the write
path = "CHANGELOG.md"           # relative to the repo or service root
unreleased_label = "Unreleased"
header_style = "keepachangelog"
```

If `CHANGELOG.md` does not exist, pezin creates it with a
Keep-a-Changelog header before writing the new section. A failure while
writing the changelog is logged as a warning and the version bump still
lands — the changelog is best-effort, never blocking.

In monorepo mode each service can override the same keys under
`[tool.pezin.services.<name>.changelog]`; per-service entries are
resolved relative to that service's root.

### Upgrading from < 0.8.0

Projects upgrading from versions before 0.8.0 will see `CHANGELOG.md`
edited automatically on the first conventional commit after upgrade.
If you maintain the changelog by hand, set `enabled = false` to keep
the previous behaviour.

## Unstaged Changes and the pre-commit Data-Loss Guard

Under the `pre-commit` framework, any unstaged changes are "parked" in a
patch file while hooks run, then re-applied afterwards. If a hook rewrites
one of those files, the re-apply can fail and the unstaged work disappears
from the worktree (it survives only in `~/.cache/pre-commit/patch*`).

Since **v0.8.1** pezin guards against this:

- **Skips the bump** when pre-commit has parked unstaged changes to a file
  pezin would rewrite (version files or `CHANGELOG.md`). The hook prints a
  message explaining the skip; stash or commit those changes, then commit
  again or run `pezin bump` to bump manually.
- **Atomic rollback**: if pezin's own write/amend path fails halfway, the
  worktree, index and `HEAD` are restored to their pre-hook state - no
  half-applied bumps, no leftover files.

Unstaged changes to *other* files never block the bump; the parked patch
restores cleanly around it.

If you were hit by this bug before v0.8.1, your "lost" work is still in the
patch file pre-commit logged (`~/.cache/pre-commit/pre-commit.log` names
it). Recover with:

```bash
git apply --exclude=<conflicting-file> --whitespace=nowarn <patch-file>
```

> **Note for local-repo consumers** (`repo: <path>, rev: HEAD` or a branch):
> pre-commit keys hook environments on the `rev` *string*, so a moved HEAD
> does **not** refresh them - `pre-commit install-hooks` alone keeps running
> the old code. Pin the rev to a released tag (edit it manually or run
> `pre-commit autoupdate`); the changed rev forces the environment rebuild.
> Verify with `pre-commit run pezin-post --all-files -v` after upgrading.

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
