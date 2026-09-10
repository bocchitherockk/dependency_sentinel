import asyncio
from contextlib import asynccontextmanager
from logging import Logger
import os

import fastapi
from fastapi import FastAPI, HTTPException

from common.logging.global_logger import get_global_logger
from common.schemas.CloneRepositoryRequest import CloneRepositoryRequest
from common.schemas.CreateBranchRequest import CreateBranchRequest
from common.schemas.UpdateFileContentRequest import UpdateFileContentRequest
from common.schemas.Directory import Directory
from common.schemas.File import File
from events.schemas.RepositoryClonedEvent import RepositoryClonedEvent

from repository_storage_service.config import REPOSITORIES_PATH
from repository_storage_service.service import (
    clone_repository_service,
    get_fs_object_service,
    update_file_content_service,
    create_branch_service,
)
from repository_storage_service.events.RepositoryClonedEventProducer import RepositoryClonedEventProducer
from repository_storage_service.events.ScanCompletedEventProducer import ScanCompletedEventProducer
from repository_storage_service.events.ManifestFilesEditedEventConsumer import ManifestFilesEditedEventConsumer


logger: Logger = get_global_logger(__name__)

os.makedirs(REPOSITORIES_PATH, exist_ok=True)
logger.info(f"Created base path for repositories: '{REPOSITORIES_PATH}'")


repository_cloned_event_producer: RepositoryClonedEventProducer = RepositoryClonedEventProducer()
scan_completed_event_producer: ScanCompletedEventProducer = ScanCompletedEventProducer()
manifest_files_edited_event_consumer: ManifestFilesEditedEventConsumer = ManifestFilesEditedEventConsumer(scan_completed_event_producer)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Gère le cycle de vie du service"""
    await repository_cloned_event_producer.start()
    await scan_completed_event_producer.start()
    await manifest_files_edited_event_consumer.start()

    manifest_files_edited_event_consumer_task = asyncio.create_task(
        manifest_files_edited_event_consumer.consume()
    )

    yield

    manifest_files_edited_event_consumer_task.cancel()
    await repository_cloned_event_producer.stop()
    await scan_completed_event_producer.stop()
    await manifest_files_edited_event_consumer.stop()


app = FastAPI(
    title="Repository Storage Service",
    description="Service responsible for storing and managing repositories",
    version="0.1.0",
    lifespan=lifespan,
)

@app.post('/clone-repository')
async def clone_repository_endpoint(
    clone_repository_request: CloneRepositoryRequest = fastapi.Body(...),
) -> dict[str, str]:
    try:
        await clone_repository_service(clone_repository_request, repository_cloned_event_producer)
        return {
            'status': 'accepted',
            'message': f'Scan process started for repository: {clone_repository_request.repository_url}',
            'repository_url': clone_repository_request.repository_url
        }
    except Exception as error:
        logger.error(f"Error while cloning repository: {str(error)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to clone repository: {str(error)}"
        )

@app.get('/repositories/{path:path}')
def get_fs_object_endpoint(
    path: str = fastapi.Path(...),
    display_files_content: bool = fastapi.Query(False),
) -> Directory | File:
    try:
        fs_object: Directory | File = get_fs_object_service(path, display_files_content)
        return fs_object
    except FileNotFoundError as error:
        raise HTTPException(
            status_code=404,
            detail=str(error),
        )

@app.put('/repositories/{path:path}')
def update_file_content_endpoint(
    path: str = fastapi.Path(...),
    update_file_content_request: UpdateFileContentRequest = fastapi.Body(...),
) -> File:
    try:
        updated_file: File = update_file_content_service(path, update_file_content_request)
        return updated_file
    except FileNotFoundError as error:
        raise HTTPException(
            status_code=404,
            detail=str(error),
        )
    except IsADirectoryError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error),
        )

@app.post('/create_branch')
async def create_branch_endpoint(
    create_branch_request: CreateBranchRequest = fastapi.Body(...),
) -> dict[str, str]:
    branch_name: str = create_branch_request.branch_name
    try:
        create_branch_service(create_branch_request)
        return {'message': f"Branch '{branch_name}' created successfully for repository '{create_branch_request.repository_name}'."}
    except FileNotFoundError as error:
        raise HTTPException(
            status_code=404,
            detail=str(error),
        )
    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error),
        )
