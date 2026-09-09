import asyncio
from contextlib import asynccontextmanager
from logging import Logger

from fastapi import FastAPI

from common.logging.global_logger import get_global_logger

from repository_scanner_service.events.RepositoryScannedEventProducer import RepositoryScannedEventProducer
from repository_scanner_service.events.RepositoryClonedEventConsumer import RepositoryClonedEventConsumer

logger: Logger = get_global_logger(__name__)

repository_scanned_event_producer: RepositoryScannedEventProducer = RepositoryScannedEventProducer()
repository_cloned_event_consumer: RepositoryClonedEventConsumer = RepositoryClonedEventConsumer(repository_scanned_event_producer)

@asynccontextmanager
async def lifespan(app: FastAPI):
    await repository_scanned_event_producer.start()
    await repository_cloned_event_consumer.start()
    repository_cloned_event_consumer_task = asyncio.create_task(
        repository_cloned_event_consumer.consume()
    )

    yield

    repository_cloned_event_consumer_task.cancel()
    await repository_scanned_event_producer.stop()
    await repository_cloned_event_consumer.stop()

app = FastAPI(
    title="Repository Scanner Service",
    description="Scans repositories, detects dependency manifest files with the LLM Service, and extracts their dependencies.",
    version="0.2.0",
    lifespan=lifespan,
)
