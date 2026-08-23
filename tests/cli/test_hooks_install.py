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
