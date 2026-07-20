from pathlib import Path
from typing import Any


IGNORED_DIRECTORIES = {
    ".git",
    ".venv",
    "node_modules",
    "target",
    "__pycache__",
    ".pytest_cache",
}


def get_fs_object_content(
    fs_object_path: Path,
    display_files_content: bool = False,
) -> dict[str, Any]:
    if fs_object_path.is_file():
        result: dict[str, Any] = {
            "name": fs_object_path.name,
            "type": "file",
        }

        if display_files_content:
            result["content"] = fs_object_path.read_text(
                encoding="utf-8",
                errors="replace",
            )

        return result

    if fs_object_path.is_dir():
        children = []

        for child in sorted(
            fs_object_path.iterdir(),
            key=lambda item: item.name.lower(),
        ):
            if (
                child.is_dir()
                and child.name in IGNORED_DIRECTORIES
            ):
                continue

            children.append(
                get_fs_object_content(
                    child,
                    display_files_content=False,
                )
            )

        return {
            "name": fs_object_path.name,
            "type": "directory",
            "children": children,
        }

    return {
        "error": "File or directory not found",
    }