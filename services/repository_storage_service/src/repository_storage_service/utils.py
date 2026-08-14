from pathlib import Path

from git import Repo

from common.schemas.Directory import Directory
from common.schemas.File import File

IGNORED_DIRECTORIES: list[str] = ['.git', '.venv', 'node_modules', 'target', '__pycache__', '.pytest_cache']

def get_fs_object(
    fs_object_path: Path,
    display_files_content: bool = False,
) -> Directory | File:
    if not fs_object_path.exists():
        raise FileNotFoundError(f"The path '{fs_object_path}' does not exist.")

    if fs_object_path.is_file():
        return File(
            path=fs_object_path,
            name=fs_object_path.name,
            content=fs_object_path.read_text(encoding="utf-8", errors="replace")
                if display_files_content else None,
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

def create_branch(repository_path: Path, branch_name: str) -> None:
    if not repository_path.exists():
        raise FileNotFoundError(f"The repository path '{repository_path}' does not exist.")

    if not branch_name:
        raise ValueError('Branch name must be a non-empty string.')

    repo = Repo(repository_path)
    repo.git.checkout('HEAD', b=branch_name)
