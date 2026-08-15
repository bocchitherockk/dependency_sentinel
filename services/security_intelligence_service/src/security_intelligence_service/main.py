from contextlib import asynccontextmanager
import asyncio

from fastapi import FastAPI
import uvicorn

from common.config import services
from common.schemas.File import File
from common.schemas.ManifestFileUpdateContext import ManifestFileUpdateContext
from events import EventConsumer, EventProducer, KafkaConfig
from events.schemas.DependenciesQueriedEvent import DependenciesQueriedEvent
from events.schemas.ScanCompletedEvent import ScanCompletedEvent
from security_intelligence_service.service import process_security_intelligence


event_producer: EventProducer = EventProducer()
event_consumer: EventConsumer = EventConsumer(
    topic=KafkaConfig.TOPIC_DEPENDENCIES_QUERIED,
    group_id=KafkaConfig.CONSUMER_GROUP_SECURITY_INTELLIGENCE_SERVICE
)

async def handle_topic_dependencies_queried(key: str, value: dict, msg):
    dependencies_queried_event: DependenciesQueriedEvent = DependenciesQueriedEvent(**value)
    repository_name: str = dependencies_queried_event.repository_name
    manifest_files_update_context: list[ManifestFileUpdateContext] = dependencies_queried_event.manifest_files_update_context

    updated_manifest_files: list[File] = await process_security_intelligence(repository_name, manifest_files_update_context)
    scan_completed_event: ScanCompletedEvent = ScanCompletedEvent(
        key=repository_name,
        updated_manifest_files=updated_manifest_files
    )
    await event_producer.publish(event=scan_completed_event)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await event_producer.start()
    await event_consumer.start()
    consumer_task = asyncio.create_task(
        event_consumer.consume(callback=handle_topic_dependencies_queried)
    )

    yield

    consumer_task.cancel()
    await event_consumer.stop()
    await event_producer.stop()

app = FastAPI(
    title="Security Intelligence Service",
    description="Microservice d'analyse de sécurité, de décision LLM et de relais vers le MCP Server.",
    lifespan=lifespan
)


def main() -> None:
    uvicorn.run(
        app,
        host=services['security-intelligence-service']['host'],
        port=services['security-intelligence-service']['port'],
    )
