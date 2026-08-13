from contextlib import asynccontextmanager
import asyncio
from fastapi import FastAPI, Body
import uvicorn
import logging

from common.config import services
from events import EventConsumer, KafkaConfig
from events.schemas.DependenciesQueriedEvent import DependenciesQueriedEvent
from security_intelligence_service.service import process_security_intelligence

logger = logging.getLogger(__name__)

event_consumer: EventConsumer = EventConsumer(
    topic=KafkaConfig.TOPIC_DEPENDENCIES_QUERIED,
    group_id=KafkaConfig.CONSUMER_GROUP_SECURITY_INTELLIGENCE_SERVICE
)

async def handle_topic_dependencies_queried(key: str, value: dict, msg):
    event = DependenciesQueriedEvent(**value)
    repository_name = event.repository_name
    manifest_files_update_context = event.manifest_files_update_context

    try:
        result = await process_security_intelligence(repository_name, manifest_files_update_context)
        logger.info(f"Analyse d'intelligence de sécurité terminée pour {repository_name} : {result['processed_count']} contextes traités.")
    except Exception as error:
        logger.error(f"Erreur dans security-intelligence-service pour {repository_name}: {error}", exc_info=True)

@asynccontextmanager
async def lifespan(app: FastAPI):
    kafka_connected = False
    try:
        await event_consumer.start()
        asyncio.create_task(event_consumer.consume(callback=handle_topic_dependencies_queried))
        kafka_connected = True
        logger.info("Connecté avec succès au broker Kafka.")
    except Exception as error:
        logger.warning(f"Kafka non disponible (localhost:9092): {error}. Le serveur HTTP démarrera en mode API standalone.")
    yield
    if kafka_connected:
        await event_consumer.stop()

app = FastAPI(
    title="Security Intelligence Service",
    description="Microservice d'analyse de sécurité, de décision LLM et de relais vers le MCP Server.",
    lifespan=lifespan
)

@app.get("/")
def health_check():
    return {"status": "ok", "service": "security-intelligence-service"}

@app.post("/process-intelligence")
async def process_intelligence_endpoint(event: DependenciesQueriedEvent = Body(...)):
    return await process_security_intelligence(event.repository_name, event.manifest_files_update_context)

def main() -> None:
    uvicorn.run(
        app,
        host=services['security-intelligence-service']['host'],
        port=services['security-intelligence-service']['port'],
    )

if __name__ == "__main__":
    main()
