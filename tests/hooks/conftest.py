"""Fixtures for end-to-end hook regression tests.

These tests exercise the real `pre-commit` framework against a throwaway
git repo. They are tagged `@pytest.mark.slow` and excluded from the
default `pytest` run; opt in with `pytest -m slow`.
"""

import os
import subprocess
import sys
from pathlib import Path
from typing import Callable

import pytest

# Use the same Python the tests run under for every hook entry, so the
# installed pezin and pre-commit binaries are reachable without depending
# on the caller's PATH.
PY = sys.executable
BIN_DIR = str(Path(PY).parent)


REFORMATTER_SCRIPT = """\
import sys
from pathlib import Path

changed = False
for path in sys.argv[1:]:
    f = Path(path)
    if not f.is_file():
        continue
    text = f.read_text()
    if not text.endswith("\\n"):
        f.write_text(text + "\\n")
        changed = True

sys.exit(1 if changed else 0)
"""


def hook_env() -> dict:
    """Env where the venv's bin dir leads PATH so child hooks find binaries."""
    env = os.environ.copy()
    env["PATH"] = BIN_DIR + os.pathsep + env.get("PATH", "")
    # Force a predictable timezone so date-stamped changelog assertions don't
    # break on hosts in unusual locales.
    env.setdefault("TZ", "UTC")
    return env


def _config_yaml(repo: Path, with_reformatter: bool) -> str:
    hooks = []
    if with_reformatter:
        hooks.append(
            "  - id: reformatter\n"
            "    name: Reformatter\n"
            f"    entry: {PY} {repo / 'reformatter.py'}\n"
            "    language: system\n"
            "    pass_filenames: true\n"
            "    stages: [pre-commit]\n"
        )
    hooks.append(
        "  - id: pezin-prepare\n"
        "    name: pezin-prepare\n"
        f"    entry: {PY} -m pezin.hooks.prepare_commit_msg\n"
        "    language: system\n"
        "    stages: [prepare-commit-msg]\n"
        "    always_run: true\n"
        "    pass_filenames: false\n"
    )
    hooks.append(
        "  - id: pezin-post\n"
        "    name: pezin-post\n"
        f"    entry: {PY} -m pezin.hooks.post_commit\n"
        "    language: system\n"
        "    stages: [post-commit]\n"
        "    always_run: true\n"
        "    pass_filenames: false\n"
    )
    return "default_stages: [pre-commit]\nrepos:\n- repo: local\n  hooks:\n" + "".join(
        hooks
    )


@pytest.fixture
def tmp_git_repo(tmp_path: Path) -> Path:
    """Isolated git repo per test, no state outside `tmp_path`."""
    repo = tmp_path / "repo"
    repo.mkdir()
    env = hook_env()

    subprocess.run(
        ["git", "init", "-q", "-b", "main"],
        cwd=repo,
        check=True,
        env=env,
    )
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=repo,
        check=True,
        env=env,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test User"],
        cwd=repo,
        check=True,
        env=env,
    )
    subprocess.run(
        ["git", "config", "commit.gpgsign", "false"],
        cwd=repo,
        check=True,
        env=env,
    )
    return repo


@pytest.fixture
def install_pezin_hooks() -> Callable[[Path], None]:
    """Install pezin hooks (prepare-commit-msg + post-commit) only."""

    def _install(repo: Path) -> None:
        (repo / ".pre-commit-config.yaml").write_text(
            _config_yaml(repo, with_reformatter=False)
        )
        subprocess.run(
            [
                PY,
                "-m",
                "pre_commit",
                "install",
                "--hook-type",
                "prepare-commit-msg",
                "--hook-type",
                "post-commit",
            ],
            cwd=repo,
            check=True,
            env=hook_env(),
            capture_output=True,
        )

    return _install


@pytest.fixture
def install_reformatter_hook() -> Callable[[Path], None]:
    """Install pezin hooks plus a pre-commit-stage reformatter."""

    def _install(repo: Path) -> None:
        (repo / "reformatter.py").write_text(REFORMATTER_SCRIPT)
        (repo / ".pre-commit-config.yaml").write_text(
            _config_yaml(repo, with_reformatter=True)
        )
        subprocess.run(
            [
                PY,
                "-m",
                "pre_commit",
                "install",
                "--hook-type",
                "pre-commit",
                "--hook-type",
                "prepare-commit-msg",
                "--hook-type",
                "post-commit",
            ],
            cwd=repo,
            check=True,
            env=hook_env(),
            capture_output=True,
        )

    return _install
