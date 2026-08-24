import asyncio
from contextlib import asynccontextmanager
from logging import Logger

from fastapi import FastAPI
import uvicorn

from repository_scanner_service.utils import scan_repository

from common.logging.global_logger import get_global_logger
from common.config import services
from common.schemas.ManifestFile import ManifestFile
from events import EventProducer, EventConsumer, KafkaConfig
from events.schemas.RepositoryClonedEvent import RepositoryClonedEvent
from events.schemas.RepositoryScannedEvent import RepositoryScannedEvent

logger: Logger = get_global_logger(__name__)

event_producer: EventProducer = EventProducer()
event_consumer: EventConsumer = EventConsumer(
    topic=KafkaConfig.TOPIC_REPOSITORY_CLONED,
    group_id=KafkaConfig.CONSUMER_GROUP_REPOSITORY_SCANNER_SERVICE
)

async def handle_topic_repository_cloned(key: str, value: dict, msg):
    repository_cloned_event: RepositoryClonedEvent = RepositoryClonedEvent(**value)
    logger.info(f"Received RepositoryClonedEvent for repository '{repository_cloned_event.repository_name}'.")
    logger.debug(f"RepositoryClonedEvent details: {repository_cloned_event}")

    repository_name = repository_cloned_event.repository_name
    repository_owner_name = repository_cloned_event.repository_owner_name
    if not repository_name:
        logger.error("Repository name cannot be empty.")
        raise ValueError("Repository name cannot be empty.")

    try:
        detected_manifest_files: list[ManifestFile] = await scan_repository(repository_name)
        repository_scanned_event: RepositoryScannedEvent = RepositoryScannedEvent(
            repository_url=repository_cloned_event.repository_url,
            repository_name=repository_name,
            repository_owner_name=repository_owner_name,
            default_branch=repository_cloned_event.default_branch,
            detected_manifest_files=detected_manifest_files,
            key=repository_name
        )
        await event_producer.publish(event=repository_scanned_event)
        logger.info(f"RepositoryScannedEvent published for repository '{repository_name}'.")
        logger.debug(f"RepositoryScannedEvent details: {repository_scanned_event}")
    except Exception as error:
        logger.error(f"Repository scan failed for repository '{repository_name}': {error}")
        raise ValueError(f"Repository scan failed: {error}") from error

@asynccontextmanager
async def lifespan(app: FastAPI):
    await event_producer.start()
    await event_consumer.start()
    consumer_task = asyncio.create_task(event_consumer.consume(handle_topic_repository_cloned))
    yield
    consumer_task.cancel()
    await event_consumer.stop()
    await event_producer.stop()

app = FastAPI(
    title="Repository Scanner Service",
    description="Scans repositories, detects dependency manifest files with the LLM Service, and extracts their dependencies.",
    version="0.2.0",
    lifespan=lifespan,
)

################## THIS IS A QUICK HACK TO SAVE TIME OR TEST #####################
################## HACK #####################
# import fastapi
# from common.schemas.File import File
# from repository_scanner_service.utils import _detect_manifest_files

# @app.post('/detect_manifests')
# async def detect_manifest_files_endpoint(request: list[File] = fastapi.Body(...)) -> list[File]:
#     detected_manifest_files: list[File] = await _detect_manifest_files(request)
#     return detected_manifest_files
################## END #####################

################## THIS IS A QUICK HACK TO SAVE TIME OR TEST #####################
################## HACK #####################
# import fastapi
# from common.schemas.File import File
# from common.schemas.ManifestFile import ManifestFile
# from repository_scanner_service.utils import _extract_dependencies

# @app.post('/extract_dependencies')
# async def extract_dependencies_endpoint(request: list[File] = fastapi.Body(...)) -> list[ManifestFile]:
#     manifest_files: list[ManifestFile] = await _extract_dependencies(request)
#     return manifest_files
################## END #####################

################## THIS IS A QUICK HACK TO SAVE TIME OR TEST #####################
################## HACK #####################
# import fastapi
# from common.schemas.ManifestFile import ManifestFile
# from repository_scanner_service.utils import scan_repository

# @app.post('/scan_repository')
# async def detect_manifest_files_endpoint(request: dict[str, str] = fastapi.Body(...)) -> list[ManifestFile]:
#     repository_name: str = request.get('repository_name')
#     manifest_files: list[ManifestFile] = await scan_repository(repository_name)
#     return manifest_files
################## END #####################

def main() -> None:
    scanner_service = services['repository-scanner-service']
    uvicorn.run(
        app,
        host=scanner_service["host"],
        port=scanner_service["port"],
    )
