"""Git hooks for version management."""

from .pre_commit import main as hook_app

__all__ = ["hook_app"]
