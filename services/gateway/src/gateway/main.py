from fastapi import FastAPI, HTTPException
import uvicorn
import logging
import requests
from contextlib import asynccontextmanager

from common.config import services
from common.schemas.CloneRepositoryRequest import CloneRepositoryRequest
from events import EventProducer, KafkaConfig  #  Import

# --- Configuration du logging ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ---  Initialisation du producer Kafka ---
event_producer = EventProducer()

# ---  Lifespan pour démarrer/arrêter le producer ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Gère le cycle de vie du service"""
    # STARTUP : Démarrer le producer Kafka
    await event_producer.start()
    logger.info(" Gateway started with Kafka producer")
    yield
    # SHUTDOWN : Arrêter le producer
    await event_producer.stop()
    logger.info(" Gateway stopped")

# --- Application FastAPI avec lifespan ---
app = FastAPI(
    title="Gateway Service",
    description="Single entry point for the platform",
    version="0.2.0",
    lifespan=lifespan,  #  Ajout
)

# --- ENDPOINT MODIFIÉ : Utiliser Kafka ---
@app.post("/scan_repository")
async def scan_repository(clone_repository_request: CloneRepositoryRequest):
    """
    Endpoint pour scanner un repository.
    Publie un événement Kafka au lieu d'appeler directement le Scanner.
    """
    repository_url = clone_repository_request.repository_url
    
    # 1. Extraire le nom du repository depuis l'URL
    repository_name = repository_url.split('/')[-1].replace('.git', '')
    
    if not repository_name:
        raise HTTPException(
            status_code=400,
            detail="Invalid repository URL"
        )
    
    # 2. Appeler le Storage Service pour cloner le repository (toujours synchrone)
    logger.info(f" Cloning repository: {repository_name}")
    
    try:
        # Appel synchrone au Storage Service
        response = requests.post(
            f'{services["repository-storage-service"]["endpoint"]}/clone_repository',
            json={"repository_url": repository_url}
        )
        response.raise_for_status()
        logger.info(f" Repository cloned: {repository_name}")
        
    except Exception as e:
        logger.error(f" Failed to clone repository: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to clone repository: {str(e)}"
        )
    
    # 3.  Publier un événement Kafka pour demander le scan
    try:
        event = {
            "event_type": "repository.scan.requested",
            "repository_name": repository_name,
            "repository_url": repository_url,
            "requested_by": "gateway",
        }
        
        await event_producer.publish(
            topic=KafkaConfig.TOPIC_SCAN_REQUESTED,
            event=event,
            key=repository_name
        )
        
        logger.info(f" Scan requested for {repository_name}")
        
        # 4. Retourner une réponse immédiate (asynchrone)
        return {
            "status": "accepted",
            "message": f"Scan requested for {repository_name}",
            "repository_name": repository_name,
            "repository_url": repository_url
        }
        
    except Exception as e:
        logger.error(f"Failed to publish scan request: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to request scan: {str(e)}"
        )

# --- Fonction main ---
def main():
    uvicorn.run(
        app,
        host=services['gateway']['host'],
        port=services['gateway']['port'],
    )

if __name__ == "__main__":
    main()