# Quick Start

Get up and running with Pumper in minutes.

## Installation

```bash
pip install pumper
```

## Setup Git Hook

**Option 1: Remote Hook (Recommended for Python projects)**

Add to your `.pre-commit-config.yaml`:

```yaml
repos:
<<<<<<< HEAD
  - repo: https://github.com/tatus9/pumper
=======
  - repo: https://github.com/tatus9/pumper
>>>>>>> 66fcc00 (docs: restructure README and create comprehensive documentation)
    rev: v1.1.0  # Use the latest version
    hooks:
      - id: pumper
```

**Option 2: Local Hook (For C/C++ and other non-Python projects)**

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
        # Optionally specify config file:
        # args: ["--config", "pumper.toml"]
```

Install the hooks:

```bash
pip install pre-commit pumper
pre-commit install --hook-type commit-msg
```

## Start Using

Just commit with conventional commit format:

```bash
git commit -m "feat: add user authentication"    # 1.0.0 → 1.1.0
<<<<<<< HEAD
git commit -m "fix: resolve login bug"           # 1.1.0 → 1.1.1
=======
git commit -m "fix: resolve login bug"           # 1.1.0 → 1.1.1
>>>>>>> 66fcc00 (docs: restructure README and create comprehensive documentation)
git commit -m "feat!: redesign API"              # 1.1.1 → 2.0.0
```

Your version files will be automatically updated! Pumper supports:

**🚀 Zero-Config Support (automatically detected):**
<<<<<<< HEAD
- **Python**: `pyproject.toml`
=======
- **Python**: `pyproject.toml`
>>>>>>> 66fcc00 (docs: restructure README and create comprehensive documentation)
- **Node.js**: `package.json`
- **Rust**: `Cargo.toml`
- **PHP**: `composer.json`

**⚙️ Pattern-Based Support (simple configuration):**
- **C/C++**: Header files (`version.h`), CMake files
- **Go**: Version constants, modules
- **Java**: Maven `pom.xml`, version constants
- **Docker**: `Dockerfile`, Kubernetes YAML
<<<<<<< HEAD
- **Any language**: Custom regex patterns
=======
- **Any language**: Custom regex patterns
>>>>>>> 66fcc00 (docs: restructure README and create comprehensive documentation)
