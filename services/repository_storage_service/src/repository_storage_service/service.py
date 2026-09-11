from logging import Logger
from pathlib import Path

from common.logging.global_logger import get_global_logger
from common.schemas.Directory import Directory
from common.schemas.File import File
from common.schemas.StartScanRequest import StartScanRequest
from common.schemas.UpdateFileContentRequest import UpdateFileContentRequest
from events.schemas.RepositoryFilesListRetrievedEvent import RepositoryFilesListRetrievedEvent

from repository_storage_service.config import REPOSITORIES_PATH
from repository_storage_service.utils import (
    get_repository_name_and_owner_name,
    clone_repository,
    get_fs_object,
    remove_repository_name_prefix,
    flatten_repository_tree,
)
from repository_storage_service.events.RepositoryFilesListRetrievedEventProducer import RepositoryFilesListRetrievedEventProducer

logger: Logger = get_global_logger(__name__)

async def start_scan_service(
    start_scan_request: StartScanRequest,
    repository_files_list_retrieved_event_producer: RepositoryFilesListRetrievedEventProducer,
) -> None:
    try:
        repository_url: str = start_scan_request.repository_url
        repository_owner_name, repository_name = get_repository_name_and_owner_name(repository_url)
        destination: Path = REPOSITORIES_PATH / repository_name

        default_branch: str = clone_repository(repository_url, destination)
        repository_content: Directory = get_fs_object(destination, display_files_content=False)
        repository_content = remove_repository_name_prefix(repository_content, REPOSITORIES_PATH)
        flattened_repository_files: list[File] = flatten_repository_tree(repository_content)

        repository_files_list_retrieved_event: RepositoryFilesListRetrievedEvent = RepositoryFilesListRetrievedEvent(
            key=repository_name,
            repository_url=repository_url,
            repository_name=repository_name,
            repository_owner_name=repository_owner_name,
            default_branch=default_branch,
            retrieved_repository_files_list=flattened_repository_files,
        )
        logger.info(f'Publishing RepositoryFilesListRetrievedEvent for repository: {repository_name}')
        logger.debug(f'RepositoryFilesListRetrievedEvent details: {repository_files_list_retrieved_event}')
        await repository_files_list_retrieved_event_producer.publish(event=repository_files_list_retrieved_event)
    except Exception as e:
        error_message: str = f"Error while starting scan for repository '{start_scan_request.repository_url}': {str(e)}"
        logger.error(error_message)
        raise RuntimeError(error_message) from e

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
