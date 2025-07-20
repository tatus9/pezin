from pathlib import Path


def find_project_root(current_path: Path = None) -> Path:
    if current_path is None:
        current_path = Path.cwd().resolve()
    starting_path = current_path
    while current_path != current_path.parent:
        if (current_path / ".git").is_dir():
            return current_path
        current_path = current_path.parent
    return starting_path
