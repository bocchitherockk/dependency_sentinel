from contextlib import asynccontextmanager
import asyncio

from fastapi import FastAPI
import uvicorn

from repository_scanner_service.utils import scan_repository

from common.config import services
from common.schemas.ManifestFile import ManifestFile
from events import EventProducer, EventConsumer, KafkaConfig
from events.schemas.RepositoryClonedEvent import RepositoryClonedEvent
from events.schemas.RepositoryScannedEvent import RepositoryScannedEvent

event_producer: EventProducer = EventProducer()
event_consumer: EventConsumer = EventConsumer(
    topic=KafkaConfig.TOPIC_REPOSITORY_CLONED,
    group_id=KafkaConfig.CONSUMER_GROUP_REPOSITORY_SCANNER_SERVICE
)

async def handle_topic_repository_cloned(key: str, value: dict, msg):
    repository_cloned_event: RepositoryClonedEvent = RepositoryClonedEvent(**value)
    repository_name = repository_cloned_event.repository_name
    if not repository_name:
        raise ValueError("Repository name cannot be empty.")

    try:
        detected_manifest_files: list[ManifestFile] = await scan_repository(repository_name)
        repository_scanned_event: RepositoryScannedEvent = RepositoryScannedEvent(
            repository_name=repository_name,
            detected_manifest_files=detected_manifest_files,
            key=repository_name
        )
        await event_producer.publish(event=repository_scanned_event)
    except Exception as error:
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

def main() -> None:
    scanner_service = services['repository-scanner-service']
    uvicorn.run(
        app,
        host=scanner_service["host"],
        port=scanner_service["port"],
    )
