from logging import Logger
import os
from pathlib import Path

from git import Repo
from github import Github
from dotenv import load_dotenv

from common.logging.global_logger import get_global_logger
from common.schemas.Directory import Directory
from common.schemas.File import File

logger: Logger = get_global_logger(__name__)


IGNORED_DIRECTORIES: list[str] = ['.git', '.venv', 'node_modules', 'target', '__pycache__', '.pytest_cache']

def get_fs_object(
    fs_object_path: Path,
    display_files_content: bool = False,
) -> Directory | File:
    if fs_object_path.is_file():
        content: str | None = None
        if display_files_content:
            content = fs_object_path.read_text(encoding="utf-8", errors="replace")
        return File(
            path=fs_object_path,
            name=fs_object_path.name,
            content=content,
        )

    if fs_object_path.is_dir():
        children: list[Directory | File] = []
        for child in sorted(
            fs_object_path.iterdir(),
            key=lambda p: (not p.is_file(), p.name.lower())
        ):
            if child.is_dir() and child.name in IGNORED_DIRECTORIES:
                continue
            children.append(get_fs_object(child, display_files_content))

        return Directory(
            path=fs_object_path,
            name=fs_object_path.name,
            children=children
        )

def remove_repository_name_prefix(foo: File | Directory, root: Path) -> File | Directory:
    new_path = foo.path.relative_to(root)
    if isinstance(foo, File):
        return File(path=new_path, name=foo.name, content=foo.content)
    elif isinstance(foo, Directory):
        new_children = [remove_repository_name_prefix(child, root) for child in foo.children]
        return Directory(path=new_path, name=foo.name, children=new_children)
