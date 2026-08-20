from logging import Logger
import os
from pathlib import Path
from urllib.parse import urlparse

from git import Repo
from github import Github
from dotenv import load_dotenv

from common.logging.global_logger import get_global_logger
from common.schemas.Directory import Directory
from common.schemas.File import File

logger: Logger = get_global_logger(__name__)

load_dotenv()
logger.info('Environment variables loaded from .env file.')
logger.debug('Environment variables: ')
logger.debug(f'GITHUB_PERSONAL_ACCESS_TOKEN: {os.getenv("GITHUB_PERSONAL_ACCESS_TOKEN")}')

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

def get_repository_name_and_owner_name(repository_url: str) -> tuple[str, str]:
    if repository_url.startswith('git@'):
        # git@github.com:owner/repo.git
        path = repository_url.split(':', 1)[1]
    else:
        # https://github.com/owner/repo.git
        path = urlparse(repository_url).path.lstrip('/')

    owner, repo = path.removesuffix('.git').split('/', 1)
    return owner, repo

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

def create_branch(repository_path: Path, branch_name: str) -> None:
    if not repository_path.exists():
        logger.error(f"The repository path '{repository_path}' does not exist.")
        raise FileNotFoundError(f"The repository path '{repository_path}' does not exist.")

    if not branch_name:
        logger.error("Branch name must be a non-empty string.")
        raise ValueError('Branch name must be a non-empty string.')

    repo = Repo(repository_path)
    repo.git.checkout('HEAD', b=branch_name)
    logger.info(f"Branch '{branch_name}' created successfully in repository at '{repository_path}'.")

def commit_and_push_changes(repository_path: Path) -> None:
    if not repository_path.exists():
        logger.error(f"The repository path '{repository_path}' does not exist.")
        raise FileNotFoundError(f"The repository path '{repository_path}' does not exist.")

    repo = Repo(repository_path)
    repo.git.add(A=True)  # Stage all changes
    repo.index.commit('Update manifest files')
    current_branch = repo.active_branch.name
    repo.git.push('-u', 'origin', current_branch)
    logger.info(f"Changes committed and pushed for repository at '{repository_path}' on branch '{current_branch}'.")

def create_pull_request(
    repository_name: str,
    repository_owner_name: str,
    default_branch: str,
    branch_name: str,
    body: str
) -> None:
    github_access_token: str = os.getenv('GITHUB_PERSONAL_ACCESS_TOKEN')
    g = Github(github_access_token)

    repo = g.get_repo(f'{repository_owner_name}/{repository_name}')

    pull_request = repo.create_pull(
        title='Dependency Sentinel auto update dependencies',
        base=default_branch,
        head=branch_name,
        body=body,
    )
    logger.info(f"Pull request created for repository '{repository_name}' on branch '{branch_name}'.")
    logger.debug(f"Pull request URL: {pull_request.html_url}")
