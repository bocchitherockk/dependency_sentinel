from contextlib import asynccontextmanager
import asyncio
from fastapi import FastAPI
import uvicorn
import logging

from common.config import services
from events import EventProducer, EventConsumer, KafkaConfig
from events.schemas.RepositoryScannedEvent import RepositoryScannedEvent
from events.schemas.ScanCompletedEvent import ScanCompletedEvent
from registry_service.service import process_registry_and_security

logger = logging.getLogger(__name__)

event_producer: EventProducer = EventProducer()
event_consumer: EventConsumer = EventConsumer(
    topic=KafkaConfig.TOPIC_REPOSITORY_SCANNED,
    group_id="consumer-group-registry-service-v2"
)

async def handle_topic_repository_scanned(key: str, value: dict, msg):
    repository_scanned_event = RepositoryScannedEvent(**value)
    repository_name = repository_scanned_event.repository_name
    detected_manifest_files = repository_scanned_event.detected_manifest_files

    try:
        report = await process_registry_and_security(repository_name, detected_manifest_files)
        scan_completed_event = ScanCompletedEvent(
            repository_name=repository_name,
            report=report,
            key=repository_name
        )
        await event_producer.publish(event=scan_completed_event)

        # Publication complémentaire pour compatibilité
        legacy_event = ScanCompletedEvent(
            repository_name=repository_name,
            report=report,
            key=repository_name
        )
        legacy_event.event_type = "repository.scan.completed"
        await event_producer.publish(event=legacy_event)
        logger.info(f"Rapport de sécurité publié avec succès pour {repository_name}")
    except Exception as error:
        logger.error(f"Erreur lors du traitement par registry-service pour {repository_name}: {error}", exc_info=True)

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

@app.get("/")
def health_check():
    return {"status": "ok", "service": "registry-service"}

@app.post("/process-scan")
async def process_scan_endpoint(event: RepositoryScannedEvent = Body(...)):
    report = await process_registry_and_security(event.repository_name, event.detected_manifest_files)
    scan_completed_event = ScanCompletedEvent(
        repository_name=event.repository_name,
        report=report,
        key=event.repository_name
    )
    await event_producer.publish(event=scan_completed_event)
    return report

def main() -> None:
    uvicorn.run(
        app,
        host=services.get('registry-service', {}).get('host', '127.0.0.1'),
        port=services.get('registry-service', {}).get('port', 8004)
    )

if __name__ == "__main__":
    main()
