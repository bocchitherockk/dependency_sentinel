import os
from pathlib import Path
from contextlib import asynccontextmanager
import asyncio

import fastapi
from fastapi import FastAPI, HTTPException
import uvicorn

from repository_storage_service.utils import (
    get_fs_object,
    remove_repository_name_prefix,
    get_repository_name_and_owner_name,
    clone_repository,
    create_branch,
    commit_and_push_changes,
    create_pull_request,
)

from common.config import services
from common.schemas.CreateBranchRequest import CreateBranchRequest
from common.schemas.UpdateFileContentRequest import UpdateFileContentRequest
from common.schemas.Directory import Directory
from common.schemas.File import File

from events import EventProducer, EventConsumer, KafkaConfig
from events.schemas.ScanStartedEvent import ScanStartedEvent
from events.schemas.RepositoryClonedEvent import RepositoryClonedEvent
from events.schemas.ManifestFilesEditedEvent import ManifestFilesEditedEvent
from events.schemas.ScanCompletedEvent import ScanCompletedEvent


os.chdir('./services/repository_storage_service/') # change current working directory
os.makedirs('./repositories', exist_ok=True)


event_producer: EventProducer = EventProducer()
scan_started_event_consumer: EventConsumer = EventConsumer(
    topic=KafkaConfig.TOPIC_SCAN_STARTED,
    group_id=KafkaConfig.CONSUMER_GROUP_REPOSITORY_STORAGE_SERVICE
)
manifest_files_edited_event_consumer: EventConsumer = EventConsumer(
    topic=KafkaConfig.TOPIC_MANIFEST_FILES_EDITED,
    group_id=KafkaConfig.CONSUMER_GROUP_REPOSITORY_STORAGE_SERVICE
)

async def handle_topic_scan_started(key: str, value: dict, msg):
    scan_started_event: ScanStartedEvent = ScanStartedEvent(**value)
    repository_url: str = scan_started_event.repository_url
    repository_owner_name, repository_name = get_repository_name_and_owner_name(repository_url)
    destination: Path = Path('./repositories') / repository_name

    default_branch: str = clone_repository(repository_url, destination)

    repository_cloned_event: RepositoryClonedEvent = RepositoryClonedEvent(
        key=repository_name,
        repository_url=repository_url,
        repository_name=repository_name,
        repository_owner_name=repository_owner_name,
        default_branch=default_branch,
    )
    await event_producer.publish(event=repository_cloned_event)

async def handle_topic_manifest_files_edited(key: str, value: dict, msg):
    manifest_files_edited_event: ManifestFilesEditedEvent = ManifestFilesEditedEvent(**value)
    if manifest_files_edited_event.summary is None:
        # If the summary is empty, it means that no manifest file was modified
        # and a git branch was not created
        # so we don't need to commit any changes or create a pull request.
        return

    repository_name: str = manifest_files_edited_event.repository_name
    repository_owner_name: str = manifest_files_edited_event.repository_owner_name

    destination: Path = Path('./repositories') / repository_name
    commit_and_push_changes(destination)
    create_pull_request(
        repository_name=repository_name,
        repository_owner_name=repository_owner_name,
        branch_name=manifest_files_edited_event.update_branch,
        body=manifest_files_edited_event.summary
    )

    scan_completed_event: ScanCompletedEvent = ScanCompletedEvent(
        key=repository_name,
        repository_name=repository_name,
        repository_owner_name=repository_owner_name,
    )
    await event_producer.publish(event=scan_completed_event)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Gère le cycle de vie du service"""
    await event_producer.start()
    await scan_started_event_consumer.start()
    await manifest_files_edited_event_consumer.start()

    scan_started_event_consumer_task = asyncio.create_task(
        scan_started_event_consumer.consume(callback=handle_topic_scan_started)
    )
    manifest_files_edited_event_consumer_task = asyncio.create_task(
        manifest_files_edited_event_consumer.consume(callback=handle_topic_manifest_files_edited)
    )

    yield

    scan_started_event_consumer_task.cancel()
    manifest_files_edited_event_consumer_task.cancel()
    await scan_started_event_consumer.stop()
    await manifest_files_edited_event_consumer.stop()
    await event_producer.stop()


app = FastAPI(
    title="Repository Storage Service",
    description="Service responsible for storing and managing repositories",
    version="0.1.0",
    lifespan=lifespan,
)


# This endpoint should be called by the repository scanner service (with display_files_content set to False) to get the list of files and directories in the repository to then use them to talk to the LLM and get the important manifest files in the repository.
# This endpoint should also be called by the dependency analyzer service (with display_files_content set to True) to get the content of the important manifest files in the repository to then parse them and get the dependencies in the repository.
# This endpoint might be called by the dependency modifier service (with display_files_content set to True) to get the content of the important manifest files in the repository to then modify them and write them back to the repository. (i might also remove the Dependency modifier service and let this Repository storage service handle the modification directly through the MCP call)
@app.get('/repositories/{path:path}')
def get_fs_object_endpoint(
    path: str = fastapi.Path(...),
    display_files_content: bool = fastapi.Query(False),
) -> Directory | File:
    root_path: Path = Path('./repositories')
    fs_object_path: Path = root_path / path
    try:
        fs_object: Directory | File = get_fs_object(fs_object_path, display_files_content)
    except FileNotFoundError:
        raise HTTPException(
            status_code=404,
            detail=f"Path '{path}' does not exist.",
        )

    return remove_repository_name_prefix(fs_object, root_path)

@app.put('/repositories/{path:path}')
def update_file_content_endpoint(
    path: str = fastapi.Path(...),
    update_file_content_request: UpdateFileContentRequest = fastapi.Body(...),
):
    root_path: Path = Path('./repositories')
    file_path = root_path / path
    if not file_path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Path '{path}' does not exist.",
        )

    if not file_path.is_file():
        raise HTTPException(
            status_code=400,
            detail=f"Path '{path}' is not a file.",
        )

    file_path.write_text(update_file_content_request.new_content, encoding='utf-8')

    return File(
        path=file_path.relative_to(root_path),
        name=file_path.name,
        content=update_file_content_request.new_content
    )

@app.post('/create_branch')
async def create_branch_endpoint(create_branch_request: CreateBranchRequest = fastapi.Body(...)):
    repository_path: Path = Path('./repositories') / create_branch_request.repository_name
    branch_name: str = create_branch_request.branch_name

    try:
        create_branch(repository_path, branch_name)
    except FileNotFoundError:
        raise HTTPException(
            status_code=404,
            detail=f"Repository '{create_branch_request.repository_name}' does not exist.",
        )
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=str(e),
        )

    return {"message": f"Branch '{branch_name}' created successfully in repository '{create_branch_request.repository_name}'."}

################## THIS IS A QUICK HACK TO SAVE TIME OR TEST #####################
################## HACK #####################
# @app.post('/clone_repository')
# async def clone_repository_endpoint(request: dict[str, str] = fastapi.Body(...)):
#     repository_url: str = request['repository_url']
#     repository_name: str = repository_url.split('/')[-1].replace('.git', '')
#     destination: Path = Path('./repositories') / repository_name

#     if not destination.exists():
#         Repo.clone_from(repository_url, destination)
#         return {"message": f"Repository '{repository_name}' cloned successfully."}
#     else:
#         # Pull the latest changes if the repository already exists
#         # Hard reset and clean to ensure the local repository state exactly matches the remote state
#         repo: Repo = Repo(destination)
#         origin = repo.remotes.origin
#         origin.fetch()
#         current_branch = repo.active_branch.name
#         repo.git.reset('--hard', f'origin/{current_branch}')
#         repo.git.clean('-fd')
#         return {"message": f"Repository '{repository_name}' already exists. Pulled latest changes."}
################## END #####################


def main() -> None:
    uvicorn.run(
        app,
        host=services['repository-storage-service']['host'],
        port=services['repository-storage-service']['port'],
        # reload=True,
    )
