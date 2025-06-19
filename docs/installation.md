# Installation Guide

## Prerequisites

- Python 3.12+
- Git repository with version file (`pyproject.toml` or `package.json`)

## Basic Installation

```bash
pip install pumper
```

## Git Hook Integration

### Method 1: Pre-commit Framework (Recommended)

Add to your `.pre-commit-config.yaml`:

```yaml
repos:
<<<<<<< HEAD
  - repo: https://github.com/tatus9/pumper
=======
  - repo: https://github.com/tatus9/pumper
>>>>>>> 66fcc00 (docs: restructure README and create comprehensive documentation)
    rev: v0.0.1  # Use the latest version
    hooks:
      - id: pumper
        name: Pumper Version Control
```

Install the hooks:

```bash
pip install pre-commit
pre-commit install --hook-type commit-msg
```

### Method 2: Direct Git Hook

```bash
cat > .git/hooks/commit-msg << 'EOF'
#!/bin/bash
pumper hook "$1"
EOF

chmod +x .git/hooks/commit-msg
```

### Method 3: Local Pre-commit Hook

```yaml
repos:
  - repo: local
    hooks:
      - id: pumper
        name: Pumper Version Control
        entry: pumper hook
        language: python
        stages: [commit-msg]
        additional_dependencies: [pumper]
```

## Verification

Test your installation:

```bash
# Make a test commit
git commit -m "feat: test pumper installation"

# Check if version was bumped in your version file
<<<<<<< HEAD
```
=======
```
>>>>>>> 66fcc00 (docs: restructure README and create comprehensive documentation)
