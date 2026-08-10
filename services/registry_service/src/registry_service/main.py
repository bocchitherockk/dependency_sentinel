from contextlib import asynccontextmanager
import asyncio

from fastapi import FastAPI
import uvicorn

from common.config import services
from common.schemas.ManifestFile import ManifestFile
from common.schemas.ManifestFileUpdateContext import ManifestFileUpdateContext
from events import EventProducer, EventConsumer, KafkaConfig
from events.schemas.RepositoryScannedEvent import RepositoryScannedEvent
from events.schemas.DependenciesQueriedEvent import DependenciesQueriedEvent
from registry_service.utils import get_manifest_file_update_context

event_producer: EventProducer = EventProducer()
event_consumer: EventConsumer = EventConsumer(
    topic=KafkaConfig.TOPIC_REPOSITORY_SCANNED,
    group_id=KafkaConfig.CONSUMER_GROUP_REGISTRY_SERVICE
)

async def handle_topic_repository_scanned(key: str, value: dict, msg):
    repository_scanned_event: RepositoryScannedEvent = RepositoryScannedEvent(**value)
    repository_name: str = repository_scanned_event.repository_name
    current_manifest_files: list[ManifestFile] = repository_scanned_event.detected_manifest_files

    manifest_files_update_context: list[ManifestFileUpdateContext] = await asyncio.gather(*[
        get_manifest_file_update_context(manifest_file)
        for manifest_file in current_manifest_files
    ])

    dependencies_queried_event: DependenciesQueriedEvent = DependenciesQueriedEvent(
        key=repository_name,
        repository_name=repository_name,
        manifest_files_update_context=manifest_files_update_context,
    )
    await event_producer.publish(event=dependencies_queried_event)

@asynccontextmanager
async def lifespan(app: FastAPI):
    await event_producer.start()
    await event_consumer.start()
    asyncio.create_task(event_consumer.consume(callback=handle_topic_repository_scanned))
    yield
    await event_consumer.stop()
    await event_producer.stop()

app = FastAPI(
    title="Registry Service",
    description="Microservice pour la résolution des versions, l'analyse de sécurité OSV et la génération du rapport LLM.",
    lifespan=lifespan
)

def main() -> None:
    uvicorn.run(
        app,
        host=services['registry-service']['host'],
        port=services['registry-service']['port'],
    )
