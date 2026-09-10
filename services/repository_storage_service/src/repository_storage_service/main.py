import asyncio
from contextlib import asynccontextmanager
from logging import Logger
import os

import fastapi
from fastapi import FastAPI, HTTPException

from common.logging.global_logger import get_global_logger
from common.schemas.StartScanRequest import StartScanRequest
from common.schemas.CreateBranchRequest import CreateBranchRequest
from common.schemas.UpdateFileContentRequest import UpdateFileContentRequest
from common.schemas.Directory import Directory
from common.schemas.File import File

from repository_storage_service.config import REPOSITORIES_PATH
from repository_storage_service.service import (
    start_scan_service,
    get_fs_object_service,
    update_file_content_service,
    create_branch_service,
)
from repository_storage_service.events.RepositoryFilesListRetrievedEventProducer import RepositoryFilesListRetrievedEventProducer
from repository_storage_service.events.ManifestFilesContentRetrievedEventProducer import ManifestFilesContentRetrievedEventProducer
from repository_storage_service.events.ManifestFilesDetectedEventConsumer import ManifestFilesDetectedEventConsumer
from repository_storage_service.events.ScanCompletedEventProducer import ScanCompletedEventProducer
from repository_storage_service.events.ManifestFilesEditedEventConsumer import ManifestFilesEditedEventConsumer


logger: Logger = get_global_logger(__name__)

os.makedirs(REPOSITORIES_PATH, exist_ok=True)
logger.info(f"Created base path for repositories: '{REPOSITORIES_PATH}'")


repository_files_list_retrieved_event_producer: RepositoryFilesListRetrievedEventProducer = RepositoryFilesListRetrievedEventProducer()
manifest_files_content_retrieved_event_producer: ManifestFilesContentRetrievedEventProducer = ManifestFilesContentRetrievedEventProducer()
manifest_files_detected_event_consumer: ManifestFilesDetectedEventConsumer = ManifestFilesDetectedEventConsumer(manifest_files_content_retrieved_event_producer)
scan_completed_event_producer: ScanCompletedEventProducer = ScanCompletedEventProducer()
manifest_files_edited_event_consumer: ManifestFilesEditedEventConsumer = ManifestFilesEditedEventConsumer(scan_completed_event_producer)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Gère le cycle de vie du service"""
    await repository_files_list_retrieved_event_producer.start()
    await manifest_files_content_retrieved_event_producer.start()
    await manifest_files_detected_event_consumer.start()
    await scan_completed_event_producer.start()
    await manifest_files_edited_event_consumer.start()

    manifest_files_detected_event_consumer_task = asyncio.create_task(
        manifest_files_detected_event_consumer.consume()
    )
    manifest_files_edited_event_consumer_task = asyncio.create_task(
        manifest_files_edited_event_consumer.consume()
    )

    yield

    manifest_files_detected_event_consumer_task.cancel()
    manifest_files_edited_event_consumer_task.cancel()

    await repository_files_list_retrieved_event_producer.stop()
    await manifest_files_content_retrieved_event_producer.stop()
    await manifest_files_detected_event_consumer.stop()
    await scan_completed_event_producer.stop()
    await manifest_files_edited_event_consumer.stop()


app = FastAPI(
    title="Repository Storage Service",
    description="Service responsible for storing and managing repositories",
    version="0.1.0",
    lifespan=lifespan,
)

@app.post('/start-scan')
async def start_scan_endpoint(
    start_scan_request: StartScanRequest = fastapi.Body(...),
) -> dict[str, str]:
    try:
        await start_scan_service(
            start_scan_request,
            repository_files_list_retrieved_event_producer
        )
        return {
            'status': 'accepted',
            'message': f'Scan process started for repository: {start_scan_request.repository_url}',
            'repository_url': start_scan_request.repository_url
        }
    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=str(error),
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
