from logging import Logger
from pathlib import Path
from urllib.parse import urlparse

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

def get_repository_name_and_owner_name(repository_url: str) -> tuple[str, str]:
    if repository_url.startswith('git@'):
        # git@github.com:owner/repo.git
        path = repository_url.split(':', 1)[1]
    else:
        # https://github.com/owner/repo.git
        path = urlparse(repository_url).path.lstrip('/')

    repository_owner_name, repository_name = path.removesuffix('.git').split('/', 1)
    return repository_owner_name, repository_name

def clone_repository(repository_url: str, destination: Path) -> str:
    default_branch: str = 'main'  # Default to 'main' if we can't determine the default branch
    if not destination.exists():
        repo: Repo = Repo.clone_from(repository_url, destination)
        default_branch = repo.active_branch.name
        logger.info(f"Repository cloned successfully from '{repository_url}' to '{destination}'. Default branch: {default_branch}")
    else:
        # Pull the latest changes if the repository already exists
        # Hard reset and clean to ensure the local repository state exactly matches the remote state
        repo: Repo = Repo(destination)
        origin = repo.remotes.origin
        origin.fetch()
        default_branch = repo.git.symbolic_ref('refs/remotes/origin/HEAD').split('/')[-1]
        repo.git.reset('--hard', f'origin/{default_branch}')
        repo.git.clean('-fd')
        logger.info(f"Repository at '{destination}' updated successfully. Default branch: {default_branch}")

    return default_branch  # Return the default branch name for further use (e.g., creating a pull request)
