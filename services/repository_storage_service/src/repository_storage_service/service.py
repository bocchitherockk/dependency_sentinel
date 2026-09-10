from logging import Logger
from pathlib import Path

from git import Repo

from common.logging.global_logger import get_global_logger
from common.schemas.Directory import Directory
from common.schemas.File import File
from common.schemas.CloneRepositoryRequest import CloneRepositoryRequest
from common.schemas.UpdateFileContentRequest import UpdateFileContentRequest
from common.schemas.CreateBranchRequest import CreateBranchRequest
from events.schemas.RepositoryClonedEvent import RepositoryClonedEvent

from repository_storage_service.config import REPOSITORIES_PATH
from repository_storage_service.utils import (
    get_repository_name_and_owner_name,
    clone_repository,
    get_fs_object,
    remove_repository_name_prefix,
)
from repository_storage_service.events.RepositoryClonedEventProducer import RepositoryClonedEventProducer

logger: Logger = get_global_logger(__name__)

async def clone_repository_service(
    clone_repository_request: CloneRepositoryRequest,
    repository_cloned_event_producer: RepositoryClonedEventProducer,
) -> None:
    repository_url: str = clone_repository_request.repository_url
    repository_owner_name, repository_name = get_repository_name_and_owner_name(repository_url)
    destination: Path = REPOSITORIES_PATH / repository_name

    default_branch: str = clone_repository(repository_url, destination)

    repository_cloned_event: RepositoryClonedEvent = RepositoryClonedEvent(
        key=repository_name,
        repository_url=repository_url,
        repository_name=repository_name,
        repository_owner_name=repository_owner_name,
        default_branch=default_branch,
    )
    logger.info(f'Publishing RepositoryClonedEvent for repository: {repository_name}')
    logger.debug(f'RepositoryClonedEvent details: {repository_cloned_event}')
    await repository_cloned_event_producer.publish(event=repository_cloned_event)

def get_fs_object_service(
    path: str,
    display_files_content: bool,
) -> Directory | File:
    fs_object_path: Path = REPOSITORIES_PATH / path
    if not fs_object_path.exists():
        error_message: str = f"Filesystem object '{path}' does not exist."
        logger.error(error_message)
        raise FileNotFoundError(error_message)

    fs_object: Directory | File = get_fs_object(fs_object_path, display_files_content)
    logger.info(f"Retrieved filesystem object '{path}' with display_files_content={display_files_content}.")
    logger.debug(f"Filesystem object details: {fs_object.model_dump_json(indent=2)}")
    return remove_repository_name_prefix(fs_object, REPOSITORIES_PATH)

def update_file_content_service(
    path: str,
    update_file_content_request: UpdateFileContentRequest,
) -> File:
    file_path: Path = REPOSITORIES_PATH / path
    if not file_path.exists():
        error_message: str = f"File '{path}' does not exist."
        logger.error(error_message)
        raise FileNotFoundError(error_message)

    if not file_path.is_file():
        error_message: str = f"Expected a file, but found a directory at '{path}'."
        logger.error(error_message)
        raise IsADirectoryError(error_message)

    file_path.write_text(update_file_content_request.new_content, encoding='utf-8')
    result: File = File(
        path=file_path.relative_to(REPOSITORIES_PATH),
        name=file_path.name,
        content=update_file_content_request.new_content
    )
    logger.info(f"Updated file at '{path}'.")
    logger.debug(f"Updated file: {result.model_dump_json(indent=2)}")
    return result

def create_branch_service(
    create_branch_request: CreateBranchRequest,
) -> None:
    repository_name: str = create_branch_request.repository_name
    # TODO: In here we need to store the repository owner name along with the repository name
    # because multiple repository owners could have used the same repository name
    repository_path: Path = REPOSITORIES_PATH / repository_name
    branch_name: str = create_branch_request.branch_name

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
