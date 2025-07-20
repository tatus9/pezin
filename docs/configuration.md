# Configuration

## Supported Version Files

Pezin automatically detects and updates versions in:

### Python Projects (pyproject.toml)
```toml
[project]
name = "your-project"
version = "1.0.0"
```

### Node.js Projects (package.json)
```json
{
  "name": "your-project",
  "version": "1.0.0"
}
```

### Custom Files
Use the `--config` flag to specify custom version files.

## Pezin Configuration

Customize behavior in your `pyproject.toml`:

```toml
[tool.pezin]
# Custom changelog file location
changelog_file = "HISTORY.md"

# Repository URL for changelog links
repo_url = "https://github.com/username/project"

# Skip changelog generation
skip_changelog = true

# Version file pattern (advanced)
version_pattern = 'version = "{version}"'
```

## CLI Configuration

### Global Options
- `--config` - Custom version file path
- `--dry-run` - Preview changes without applying
- `--skip-changelog` - Skip changelog updates

### Pre-release Labels
- `--pre-release alpha` - Add alpha label (1.0.0 → 1.1.0-alpha.1)
- `--pre-release beta` - Add beta label (1.0.0 → 1.1.0-beta.1)
- `--pre-release rc` - Add release candidate label (1.0.0 → 1.1.0-rc.1)

## Environment Variables

- `PEZIN_DEBUG=1` - Enable verbose logging
- `PEZIN_CONFIG` - Default config file path
