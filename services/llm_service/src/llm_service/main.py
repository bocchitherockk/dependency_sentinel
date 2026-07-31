from typing import Any
from fastapi import FastAPI, Body, Query
import uvicorn
import logging
from contextlib import asynccontextmanager
import asyncio

from common.config import services
from llm_service.llm_selector import LLMSelector
from events import EventProducer, EventConsumer, KafkaConfig  #  Import

# --- Configuration du logging ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ---  Initialisation Kafka ---
event_producer = EventProducer()
event_consumer = EventConsumer(
    topic=KafkaConfig.TOPIC_LLM_REQUESTS,
    group_id=KafkaConfig.CONSUMER_GROUP_LLM
)

# ---  Callback pour traiter les requêtes LLM ---
async def handle_llm_request(key: str, value: dict, msg):
    """
    Callback appelé quand un message arrive sur llm.requests
    
    Traite les différents types de requêtes :
    - "detect_manifests" : Détecte les fichiers manifest
    - "extract_dependencies" : Extrait les dépendances
    """
    request_id = value.get("request_id")
    task_type = value.get("task_type")
    payload = value.get("payload")
    repository_name = value.get("repository_name")
    
    logger.info(f" Processing LLM request {request_id} - {task_type}")
    
    try:
        # Sélectionner le modèle LLM (par défaut qwen3:8b)
        # Tu peux aussi choisir le modèle en fonction du type de tâche
        if task_type == "detect_manifests":
            model = LLMSelector.get_llm_model("qwen3:8b")
        else:
            model = LLMSelector.get_llm_model("qwen2.5-coder:1.5b")
        
        # --- Traiter selon le type de requête ---
        if task_type == "detect_manifests":
            # Récupérer la liste des fichiers
            files = payload.get("files", [])
            logger.info(f" Detecting manifests from {len(files)} files")
            
            # Appeler la méthode existante
            result = await model.detect_manifests(files)
            
            # TODO: Publier la réponse sur un topic dédié (llm.responses)
            # Dans une version future, on publiera la réponse pour que
            # le Scanner puisse la récupérer asynchrone.
            # Pour l'instant, on loggue simplement le résultat.
            logger.info(f" LLM request {request_id} completed (detect_manifests)")
            logger.info(f" Found {len(result.get('manifest_files', []))} manifests")
            
        elif task_type == "extract_dependencies":
            # Récupérer le fichier manifest
            manifest_file = payload.get("manifest_file", {})
            logger.info(f" Extracting dependencies from {manifest_file.get('path', 'unknown')}")
            
            # Appeler la méthode existante
            result = await model.extract_dependencies(manifest_file)
            
            # TODO: Publier la réponse sur un topic dédié (llm.responses)
            logger.info(f" LLM request {request_id} completed (extract_dependencies)")
            
            # Extraire les infos pour le log
            deps = result.get('manifest_file', {}).get('dependencies', [])
            dev_deps = result.get('manifest_file', {}).get('dev-dependencies', [])
            logger.info(f"   Found {len(deps)} dependencies, {len(dev_deps)} dev dependencies")
            
        else:
            raise ValueError(f"Unknown task type: {task_type}")
        
    except Exception as e:
        logger.error(f" LLM request {request_id} failed: {e}")
        # TODO: Publier l'erreur sur un topic d'erreur (llm.responses.failed)
        # await event_producer.publish(
        #     topic="llm.responses.failed",
        #     event={
        #         "request_id": request_id,
        #         "error": str(e)
        #     }
        # )

# ---  Lifespan pour gérer le cycle de vie ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Gère le cycle de vie du service"""
    # STARTUP : Démarrer Kafka
    await event_producer.start()
    await event_consumer.start()
    
    # Démarrer la boucle de consommation en arrière-plan
    consumer_task = asyncio.create_task(event_consumer.consume(handle_llm_request))
    
    logger.info(" LLM Service started with Kafka")
    yield
    
    # SHUTDOWN : Arrêter Kafka
    consumer_task.cancel()
    await event_consumer.stop()
    await event_producer.stop()
    logger.info("LLM Service stopped")

# --- Application FastAPI avec lifespan ---
app = FastAPI(
    title="LLM Service",
    description="LLM Service for dependency analysis",
    version="0.2.0",
    lifespan=lifespan,  #  Ajout
)

# ---  Endpoints REST existants (gardés pour compatibilité) ---
@app.post("/detect-manifests")
async def detect_manifests(
    files: list[str] = Body(...),
    model_name: str | None = Query(None)
):
    """
    Endpoint REST pour détecter les manifests (compatibilité)
    """
    model = LLMSelector.get_llm_model(model_name)
    return await model.detect_manifests(files)

@app.post("/extract-dependencies")
async def extract_dependencies(
    manifest_file: dict[str, Any] = Body(...),
    model_name: str | None = Query(None)
):
    """
    Endpoint REST pour extraire les dépendances (compatibilité)
    """
    model = LLMSelector.get_llm_model(model_name)
    return await model.extract_dependencies(manifest_file)

# --- Fonction main ---
def main() -> None:
    uvicorn.run(
        app,
        host=services['llm-service']['host'],
        port=services['llm-service']['port'],
    )

if __name__ == "__main__":
    main()