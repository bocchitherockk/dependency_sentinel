from pathlib import Path

from common.schemas.Directory import Directory
from common.schemas.File import File

def get_fs_object_content(
    fs_object_path: Path,
    display_files_content: bool = False,
) -> Directory | File:
    IGNORED_DIRECTORIES = {
        ".git",
        ".venv",
        "node_modules",
        "target",
        "__pycache__",
        ".pytest_cache",
    }

    if not fs_object_path.exists():
        raise ValueError(f"Path '{fs_object_path}' does not exist.")

    if fs_object_path.is_file():
        result: File = File(
            path='/'.join(fs_object_path.parts[1::]),
            name=fs_object_path.name,
        )
        if display_files_content:
            result.content = fs_object_path.read_text(
                encoding="utf-8",
                errors="replace",
            )
        return result

    if fs_object_path.is_dir():
        children: list[Directory | File] = []
        for child in sorted(
            fs_object_path.iterdir(),
            key=lambda item: item.name.lower(),
        ):
            if child.is_dir() and child.name in IGNORED_DIRECTORIES:
                continue
            children.append(get_fs_object_content(child, display_files_content))

        return Directory(
            path='/'.join(fs_object_path.parts[1::]),
            name=fs_object_path.name,
            children=children
        )
