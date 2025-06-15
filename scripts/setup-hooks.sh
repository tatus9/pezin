#!/bin/bash
set -e

echo "Removing existing hooks..."
pre-commit uninstall

echo "Installing commit-msg hook..."
pre-commit install --hook-type commit-msg

echo "Running pre-commit autoupdate..."
pre-commit autoupdate

# Force reload hooks
rm -f .git/hooks/* || true
pre-commit install --hook-type commit-msg --overwrite

echo "Hooks installed successfully"
