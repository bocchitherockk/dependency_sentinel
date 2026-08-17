from contextlib import asynccontextmanager
import asyncio

from fastapi import FastAPI
import uvicorn

from common.config import services
from common.schemas.File import File
from common.schemas.ManifestFileUpdateContext import ManifestFileUpdateContext
from events import EventConsumer, EventProducer, KafkaConfig
from events.schemas.DependenciesQueriedEvent import DependenciesQueriedEvent
from events.schemas.ManifestFilesEditedEvent import ManifestFilesEditedEvent
from security_intelligence_service.service import analyze_update_context_and_update_manifests


event_producer: EventProducer = EventProducer()
event_consumer: EventConsumer = EventConsumer(
    topic=KafkaConfig.TOPIC_DEPENDENCIES_QUERIED,
    group_id=KafkaConfig.CONSUMER_GROUP_SECURITY_INTELLIGENCE_SERVICE
)

async def handle_topic_dependencies_queried(key: str, value: dict, msg):
    dependencies_queried_event: DependenciesQueriedEvent = DependenciesQueriedEvent(**value)
    repository_name: str = dependencies_queried_event.repository_name
    repository_owner_name: str = dependencies_queried_event.repository_owner_name
    manifest_files_update_context: list[ManifestFileUpdateContext] = dependencies_queried_event.manifest_files_update_context

    summary: str = await analyze_update_context_and_update_manifests(
        repository_name,
        manifest_files_update_context,
    )
    manifest_files_edited_event: ManifestFilesEditedEvent = ManifestFilesEditedEvent(
        key=repository_name,
        repository_url=dependencies_queried_event.repository_url,
        repository_name=repository_name,
        repository_owner_name=repository_owner_name,
        default_branch=dependencies_queried_event.default_branch,
        summary=summary,
    )
    await event_producer.publish(event=manifest_files_edited_event)


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
