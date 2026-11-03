from logging import Logger
import os
from pathlib import Path
from urllib.parse import urlparse

from git import Repo
from github import Github

from common.logging.global_logger import get_global_logger
from common.schemas.Directory import Directory
from common.schemas.File import File

from repository_storage_service.config import REPOSITORIES_PATH

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

def flatten_repository_tree(node: Directory | File) -> list[File]:
    if isinstance(node, File):
        return [node]
    elif isinstance(node, Directory):
        files: list[File] = []
        for child in node.children:
            child_files: list[File] = flatten_repository_tree(child)
            files.extend(child_files)
        return files

def retrieve_manifest_files_content(manifest_files: list[File]) -> list[File]:
    result: list[File] = []
    for manifest_file in manifest_files:
        manifest_file_with_content: File = get_fs_object(REPOSITORIES_PATH / manifest_file.path, display_files_content=True)
        manifest_file_with_content = remove_repository_name_prefix(manifest_file_with_content, REPOSITORIES_PATH)
        result.append(manifest_file_with_content)
        logger.info(f'Retrieved content for manifest file: {str(manifest_file.path)}')
        logger.debug(f'Manifest file content: {manifest_file_with_content.content}')
    return result

def commit_and_push_changes(repository_path: Path) -> None:
    if not repository_path.exists():
        logger.error(f"The repository path '{repository_path}' does not exist.")
        raise FileNotFoundError(f"The repository path '{repository_path}' does not exist.")

    repo = Repo(repository_path)
    repo.git.add(A=True)  # Stage all changes
    try:
        repo.index.commit('Update manifest files')
    except Exception as e:
        logger.warning(f"Git commit notice: {e}")
    current_branch = repo.active_branch.name

    github_access_token = os.getenv('GITHUB_PERSONAL_ACCESS_TOKEN')
    remote_url = repo.remotes.origin.url.replace('www.github.com', 'github.com') # we remove the 'www' prefix because it can cause issues with authentication (github am i right ??, billion dollar company)
    if remote_url.startswith('https://') and '@' not in remote_url and github_access_token:
        auth_url = remote_url.replace('https://', f'https://{github_access_token}:@')
        repo.git.push(auth_url, f'{current_branch}:{current_branch}')
    else:
        repo.git.push('origin', current_branch)

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
    logger.info(f"PULL REQUEST URL: {pull_request.html_url}")
    print(f"\n========================================\nPULL REQUEST CREATED: {pull_request.html_url}\n========================================\n", flush=True)

def create_git_branch(
    repository_name: str,
    branch_name: str,
) -> None:
    repository_path: Path = REPOSITORIES_PATH / repository_name

    if not repository_path.exists():
        error_message: str = f"Repository '{repository_path}' does not exist."
        logger.error(error_message)
        raise FileNotFoundError(error_message)

    if not branch_name:
        error_message: str = f"Invalid branch name '{branch_name}' for repository '{repository_name}'."
        logger.error(error_message)
        raise ValueError(error_message)

    repo: Repo = Repo(repository_path)
    repo.git.checkout('HEAD', b=branch_name)
    logger.info(f"Branch '{branch_name}' created successfully for repository '{repository_name}'.")
