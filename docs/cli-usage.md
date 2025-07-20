# CLI Usage

## Manual Version Bumping

### Basic Commands

```bash
# Automatic bump based on commits since last tag
pezin minor

# Specific bump types
pezin major    # 1.0.0 → 2.0.0
pezin minor    # 1.0.0 → 1.1.0
pezin patch    # 1.0.0 → 1.0.1
```

### Dry Run Mode

Preview changes without applying them:

```bash
pezin minor --dry-run
pezin major --dry-run --config package.json
```

### Pre-release Versions

```bash
# Add pre-release labels
pezin minor --pre-release alpha   # 1.0.0 → 1.1.0-alpha.1
pezin patch --pre-release beta    # 1.0.0 → 1.0.1-beta.1
pezin major --pre-release rc      # 1.0.0 → 2.0.0-rc.1
```

### Custom Configuration

```bash
# Use custom version file
pezin patch --config package.json
pezin minor --config src/version.py

# Skip changelog update
pezin minor --skip-changelog

# Custom changelog file
pezin patch --changelog HISTORY.md
```

### Force Specific Messages

Override automatic commit detection:

```bash
# Force bump with specific commit message
pezin patch --message "fix: urgent security patch"
pezin minor --message "feat: new user dashboard"
```

## Git Hook Command

Process commit message files (used by git hooks):

```bash
# Process commit message file
pezin hook /path/to/commit/message

# With prepare-commit-msg arguments
pezin hook /path/to/commit/message commit sha123
```

## Examples

### Typical Workflow

```bash
# Development workflow
git commit -m "feat: add user authentication"  # Auto-bumps to 1.1.0
git commit -m "fix: resolve login bug"         # Auto-bumps to 1.1.1
git commit -m "feat!: redesign API"           # Auto-bumps to 2.0.0

# Manual override when needed
pezin patch --message "chore: update deps" --force-patch
```

### Release Workflow

```bash
# Create pre-release
pezin minor --pre-release rc    # 1.0.0 → 1.1.0-rc.1

# Test and iterate
pezin patch --pre-release rc    # 1.1.0-rc.1 → 1.1.0-rc.2

# Final release
pezin minor                     # 1.1.0-rc.2 → 1.1.0
```

### Multi-project Setup

```bash
# Frontend (package.json)
pezin minor --config frontend/package.json

# Backend (pyproject.toml)
pezin patch --config backend/pyproject.toml

# Shared library
pezin major --config libs/shared/pyproject.toml
```
