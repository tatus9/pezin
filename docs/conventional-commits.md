# Conventional Commits Guide

Pezin follows the [Conventional Commits](https://www.conventionalcommits.org/) specification.

## Basic Format

```
<type>[optional scope]: <description>

[optional body]

[optional footer(s)]
```

## Version Bump Rules

| Commit Type | Version Bump | Example |
|-------------|--------------|---------|
| `feat:` | Minor (1.0.0 → 1.1.0) | `feat: add user authentication` |
| `fix:` | Patch (1.0.0 → 1.0.1) | `fix: resolve login bug` |
| `feat!:` or `BREAKING CHANGE:` | Major (1.0.0 → 2.0.0) | `feat!: redesign API` |

## Other Commit Types (No Version Bump)

- `docs:` - Documentation changes
- `style:` - Code style/formatting
- `refactor:` - Code refactoring
- `perf:` - Performance improvements
- `test:` - Adding/updating tests
- `chore:` - Maintenance tasks
- `ci:` - CI/CD configuration
- `build:` - Build system changes

## Special Footer Tokens

Control version bumping with footer tokens:

```bash
# Skip version bump
git commit -m "feat: new feature

[skip-bump]"

# Force specific bump
git commit -m "docs: update readme

[force-patch]"

# Add pre-release label
git commit -m "feat: beta feature

[pre-release=beta]"
```

### Available Tokens

- `[skip-bump]` - Skip version bump entirely
- `[force-major]` - Force major bump (1.0.0 → 2.0.0)
- `[force-minor]` - Force minor bump (1.0.0 → 1.1.0)
- `[force-patch]` - Force patch bump (1.0.0 → 1.0.1)
- `[pre-release=label]` - Add pre-release label (alpha, beta, rc)

## Examples

### Feature Additions
```bash
git commit -m "feat: add user authentication"
git commit -m "feat(api): add new user endpoint"
```

### Bug Fixes
```bash
git commit -m "fix: resolve login validation issue"
git commit -m "fix(ui): fix button alignment"
```

### Breaking Changes
```bash
git commit -m "feat!: redesign authentication API"
git commit -m "feat: new auth system

BREAKING CHANGE: The authentication API has been completely redesigned."
```

### No Version Bump
```bash
git commit -m "docs: update installation guide"
git commit -m "chore: update dependencies"
```
