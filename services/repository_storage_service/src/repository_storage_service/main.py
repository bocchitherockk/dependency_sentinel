import os
from pathlib import Path
from contextlib import asynccontextmanager
import asyncio

import fastapi
from fastapi import FastAPI, HTTPException
import uvicorn
from git import Repo

from repository_storage_service.utils import get_fs_object_content

from common.config import services
from common.schemas.UpdateFileContentRequest import UpdateFileContentRequest
from common.schemas.Directory import Directory
from common.schemas.File import File
from events import EventProducer, EventConsumer, KafkaConfig
from events.schemas.ScanStartedEvent import ScanStartedEvent
from events.schemas.RepositoryClonedEvent import RepositoryClonedEvent


os.chdir('./services/repository_storage_service/') # change current working directory
os.makedirs('./repositories', exist_ok=True)


event_producer: EventProducer = EventProducer()
event_consumer: EventConsumer = EventConsumer(
    topic=KafkaConfig.TOPIC_SCAN_STARTED,
    group_id=KafkaConfig.CONSUMER_GROUP_REPOSITORY_STORAGE_SERVICE
)

async def handle_topic_scan_started(key: str, value: dict, msg):
    scan_started_event: ScanStartedEvent = ScanStartedEvent(**value)
    repository_url = scan_started_event.repository_url
    repository_name = repository_url.split('/')[-1].replace('.git', '')
    destination: Path = Path('./repositories/' + repository_name)
    if not destination.exists():
        Repo.clone_from(repository_url, destination)
    else:
        # fetch the latest changes if the repository already exists
        # TODO: i think there is an error here, make sure that the content of the repository is updated correctly, because i think pulling when the .git is up to date but there are changes in the working directory will not update the working directory, so maybe we need to do a hard reset or something like that
        repo = Repo(destination)
        origin = repo.remotes.origin
        origin.pull()

    repository_cloned_event = RepositoryClonedEvent(repository_name=repository_name, key=repository_name)

    await event_producer.publish(event=repository_cloned_event)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Gère le cycle de vie du service"""
    await event_producer.start()
    await event_consumer.start()
    consumer_task = asyncio.create_task(
        event_consumer.consume(callback=handle_topic_scan_started)
    )

    yield

    consumer_task.cancel()
    await event_consumer.stop()
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
@app.get("/repositories/{path:path}")
def browse_filesystem_endpoint(
    path: str = fastapi.Path(...),
    display_files_content: bool = fastapi.Query(False),
) -> Directory | File:
    fs_object_path = Path("./repositories") / path

    if not fs_object_path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Path '{path}' does not exist.",
        )

    return get_fs_object_content(
        fs_object_path,
        display_files_content,
    )

# This endpoint should be called by the Dependency modifier service (which is initially called by the LLM through the MCP server)
# note: the Dependency modifier service will be responsible for providing correct content to be written in the file
# TODO: this endpoint needs some changes, but for now i will leave it, up until we need to change the content of files
@app.put('/repositories/{path:path}')
def update_file_content_endpoint(
    path: str = fastapi.Path(...),
    update_file_content_request: UpdateFileContentRequest = fastapi.Body(...),
):
    file_path = Path(f'./repositories/{path}')
    if not file_path.exists():
        return { 'error': 'File not found' }

    if not file_path.is_file():
        return { 'error': 'Path is not a file' }

    with open(file_path, 'w') as f:
        f.write(update_file_content_request.new_content)

    return { 'message': f'File {path} updated successfully.' }

def main() -> None:
    uvicorn.run(
        app,
        host=services['repository-storage-service']['host'],
        port=services['repository-storage-service']['port'],
        # reload=True,
    )
