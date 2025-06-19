# Troubleshooting

## Common Issues

### Hook Not Running

**Symptoms:** No version bump occurs after commits
**Solutions:**
1. Ensure commit-msg hook is installed:
   ```bash
   pre-commit install --hook-type commit-msg
   ```
2. Check commit message format follows conventional commits
3. Verify hook is executable:
   ```bash
   ls -la .git/hooks/commit-msg
   ```

### Version Not Updating

**Symptoms:** Hook runs but version file unchanged
**Solutions:**
1. Verify version file format:
   ```bash
   # Python projects
   grep -n "version" pyproject.toml

   # Node.js projects
   grep -n "version" package.json
   ```
2. Check commit type triggers version bump:
   - `feat:` → minor bump
   - `fix:` → patch bump
   - Other types → no bump

### Amend Commits Being Processed

**Symptoms:** Version bumps on `git commit --amend`
**Check:** This should be automatically detected and skipped. If not:
1. Check logs: `cat .git/pumper.log`
2. Verify amend detection is working
3. Report as issue if persisting

### Rebase Operations Failing

**Symptoms:** `git rebase -i` fails with pumper errors
**Solutions:**
1. Ensure only commit-msg hook is active:
   ```bash
   ls .git/hooks/ | grep -E "(prepare-commit-msg|commit-msg)"
   # Should only show: commit-msg
   ```
2. Remove conflicting hooks:
   ```bash
   rm .git/hooks/prepare-commit-msg
   ```

## Debug Mode

Enable detailed logging:

```bash
export PUMPER_DEBUG=1
git commit -m "feat: test commit"
```

Check logs:
```bash
cat .git/pumper.log
```

## Log Analysis

### Successful Operation
```
INFO | 🚀 Pumper hook starting...
INFO | Processing commit message: 'feat: add new feature'
INFO | ✅ Not an amend - proceeding with version bump
INFO | Current version: 1.0.0
INFO | Bumping to: 1.1.0
INFO | ✨ Version bumped to 1.1.0
```

### Amend Detection
```
INFO | === Starting amend detection ===
INFO | ✓ ORIG_HEAD matches current HEAD - AMEND DETECTED
INFO | 🛑 AMEND DETECTED - Skipping version bump
```

### Rebase Detection
```
INFO | ✓ Git rebase operation in progress - SKIPPING VERSION BUMP
```

## Configuration Issues

### Invalid Version File
```bash
# Check file format
cat pyproject.toml | grep -A5 "\[project\]"

# Should contain:
# [project]
# version = "1.0.0"
```

### Permission Issues
```bash
# Fix hook permissions
chmod +x .git/hooks/commit-msg

# Check file ownership
ls -la .git/hooks/commit-msg
```

## Getting Help

1. **Check logs first:** `cat .git/pumper.log`
2. **Enable debug mode:** `export PUMPER_DEBUG=1`
3. **Verify configuration:** Check version file format
4. **Test manually:** `pumper hook --help`

## Reporting Issues

When reporting issues, include:
1. Pumper version: `pip show pumper`
2. Git version: `git --version`
3. Operating system
4. Complete error message
5. Debug logs from `.git/pumper.log`
6. Sample commit that fails
