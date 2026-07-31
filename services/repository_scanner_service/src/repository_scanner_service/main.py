import uvicorn
from fastapi import FastAPI, HTTPException
from contextlib import asynccontextmanager
import asyncio
import logging

from common.config import services
from repository_scanner_service.utils import scan_repository
from events import EventProducer, EventConsumer, KafkaConfig  #  Import

# --- Configuration du logging ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ---  Initialisation Kafka ---
event_producer = EventProducer()
event_consumer = EventConsumer(
    topic=KafkaConfig.TOPIC_SCAN_REQUESTED,
    group_id=KafkaConfig.CONSUMER_GROUP_SCANNER
)

# ---  Callback pour traiter les messages Kafka ---
async def handle_scan_request(key: str, value: dict, msg):
    """
    Callback appelé quand un message arrive sur repository.scan.requested
    """
    repository_name = value.get("repository_name")
    repository_url = value.get("repository_url")
    
    logger.info(f" Received scan request for {repository_name}")
    
    try:
        # 1. Exécuter le scan (fonction existante)
        result = await scan_repository(
            repository_name=repository_name,
            repository_url=repository_url
        )
        
        # 2. Publier événement de succès
        await event_producer.publish(
            topic=KafkaConfig.TOPIC_SCAN_COMPLETED,
            event={
                "event_type": "repository.scan.completed",
                "repository_name": repository_name,
                "manifests": result.get("manifests", []),
                "total_dependencies": result.get("total_dependencies", 0)
            },
            key=repository_name
        )
        
        logger.info(f" Scan completed for {repository_name}")
        
    except Exception as e:
        # 3. Publier événement d'échec
        await event_producer.publish(
            topic=KafkaConfig.TOPIC_SCAN_FAILED,
            event={
                "event_type": "repository.scan.failed",
                "repository_name": repository_name,
                "error": str(e),
                "step": "scan_execution"
            },
            key=repository_name
        )
        
        logger.error(f" Scan failed for {repository_name}: {e}")

# ---  Lifespan pour gérer le cycle de vie ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Gère le cycle de vie du service"""
    # STARTUP : Démarrer Kafka
    await event_producer.start()
    await event_consumer.start()
    
    # Démarrer la boucle de consommation en arrière-plan
    consumer_task = asyncio.create_task(event_consumer.consume(handle_scan_request))
    
    logger.info(" Repository Scanner started with Kafka")
    yield
    
    # SHUTDOWN : Arrêter Kafka
    consumer_task.cancel()
    await event_consumer.stop()
    await event_producer.stop()
    logger.info(" Repository Scanner stopped")

# --- Application FastAPI avec lifespan ---
app = FastAPI(
    title="Repository Scanner Service",
    description=(
        "Scans repositories, detects dependency manifest files "
        "with the LLM Service, and extracts their dependencies."
    ),
    version="0.2.0",
    lifespan=lifespan,  
)

# ---  Endpoint REST existant  ---
@app.get("/scan/{repository_name}")
async def scan(repository_name: str):
    """
    Endpoint REST pour scanner un repo (garde la compatibilité avec l'ancien système)
    """
    repository_name = repository_name.strip()

    if not repository_name:
        raise HTTPException(
            status_code=400,
            detail="Repository name cannot be empty.",
        )

    try:
        return await scan_repository(repository_name)
    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=f"Repository scan failed: {error}",
        ) from error

def main() -> None:
    """
    Start the Repository Scanner Service.
    """
    scanner_service = services['repository-scanner-service']
    uvicorn.run(
        app,
        host=scanner_service["host"],
        port=scanner_service["port"],
    )

if __name__ == "__main__":
    main()