import asyncio
from contextlib import asynccontextmanager
from logging import Logger

from fastapi import FastAPI

from common.logging.global_logger import get_global_logger

from security_intelligence_service.events.DependenciesQueriedEventConsumer import DependenciesQueriedEventConsumer
from security_intelligence_service.events.ManifestFilesEditedEventProducer import ManifestFilesEditedEventProducer

logger: Logger = get_global_logger(__name__)

manifest_files_edited_event_producer: ManifestFilesEditedEventProducer = ManifestFilesEditedEventProducer()
dependencies_queried_event_consumer: DependenciesQueriedEventConsumer = DependenciesQueriedEventConsumer(manifest_files_edited_event_producer)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await manifest_files_edited_event_producer.start()
    await dependencies_queried_event_consumer.start()
    dependencies_queried_event_consumer_task = asyncio.create_task(
        dependencies_queried_event_consumer.consume()
    )

    yield

    dependencies_queried_event_consumer_task.cancel()
    await manifest_files_edited_event_producer.stop()
    await dependencies_queried_event_consumer.stop()

app = FastAPI(
    title="Security Intelligence Service",
    description="Microservice d'analyse de sécurité, de décision LLM et de relais vers le MCP Server.",
    lifespan=lifespan
)
