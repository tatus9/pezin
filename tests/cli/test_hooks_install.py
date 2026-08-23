"""Tests for git hook script generation (pezin install-hooks)."""

from pathlib import Path

from pezin.cli.hooks import create_hook_script


def test_generated_hook_runs_main_through_typer(tmp_path: Path) -> None:
    """The generated script must invoke typer.run(main), not main().

    Every hook ``main()`` is typer-decorated, so calling it directly raises
    ``'OptionInfo' object has no attribute 'suffix'``. Going through
    ``typer.run`` lets typer parse argv and bind the parameters correctly.
    """
    hook_path = create_hook_script("post-commit", "pezin.hooks.post_commit", tmp_path)

    script = hook_path.read_text()
    assert "import typer" in script
    assert "typer.run(main)" in script
    # Guard against regressing to the direct-call form.
    assert not any(line.strip() == "main()" for line in script.splitlines())


def test_generated_hook_script_executes(tmp_path: Path, monkeypatch) -> None:
    """The generated script must actually run (the OptionInfo/suffix bug was
    a runtime failure, not a string match). Executed outside a git repo, the
    hook degrades to a clean exit rather than a traceback."""
    import subprocess
    import sys

    hook_path = create_hook_script("post-commit", "pezin.hooks.post_commit", tmp_path)
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.email", "t@e.com"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "T"], cwd=tmp_path, check=True)
    (tmp_path / "README.md").write_text("seed\n")
    subprocess.run(["git", "add", "-A"], cwd=tmp_path, check=True)
    subprocess.run(
        ["git", "commit", "-q", "-m", "chore: seed", "--no-verify"],
        cwd=tmp_path,
        check=True,
    )
    monkeypatch.chdir(tmp_path)

    result = subprocess.run(
        [sys.executable, str(hook_path)],
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert result.returncode == 0, result.stderr
    assert "OptionInfo" not in result.stderr
    assert "Traceback" not in result.stderr
