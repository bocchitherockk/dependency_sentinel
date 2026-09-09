import asyncio
from contextlib import asynccontextmanager
from logging import Logger

from fastapi import FastAPI, HTTPException

from common.logging.global_logger import get_global_logger

from registry_service.events.DependenciesQueriedEventProducer import DependenciesQueriedEventProducer
from registry_service.events.RepositoryScannedEventConsumer import RepositoryScannedEventConsumer
from registry_service.service import get_supported_registries_service


logger: Logger = get_global_logger(__name__)

dependencies_queried_event_producer: DependenciesQueriedEventProducer = DependenciesQueriedEventProducer()
repository_scanned_event_consumer: RepositoryScannedEventConsumer = RepositoryScannedEventConsumer(dependencies_queried_event_producer)

@asynccontextmanager
async def lifespan(app: FastAPI):
    await dependencies_queried_event_producer.start()
    await repository_scanned_event_consumer.start()
    repository_scanned_event_consumer_task = asyncio.create_task(
        repository_scanned_event_consumer.consume()
    )

    yield

    repository_scanned_event_consumer_task.cancel()
    await dependencies_queried_event_producer.stop()
    await repository_scanned_event_consumer.stop()


app = FastAPI(
    title="Registry Service",
    description="Microservice pour la résolution des versions, l'analyse de sécurité OSV et la génération du rapport LLM.",
    lifespan=lifespan
)

@app.get('/supported-registries')
async def get_supported_registries_endpoint() -> list[str]:
    try:
        return get_supported_registries_service()
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )
