import httpx
import asyncio
from typing import Any
import logging
import uuid  #  Pour générer des ID uniques

from common.config import services
from events import EventProducer, KafkaConfig  # Import

# --- Configuration du logging ---
logger = logging.getLogger(__name__)

# --- Producer pour envoyer les requêtes LLM ---
event_producer = EventProducer()

# ---  Fonction pour publier une requête LLM ---
async def _publish_llm_request(
    request_id: str,
    repository_name: str,
    task_type: str,
    payload: dict[str, Any]
):
    """
    Publie une requête LLM sur le topic llm.requests
    """
    await event_producer.publish(
        topic=KafkaConfig.TOPIC_LLM_REQUESTS,
        event={
            "event_type": "llm.request",
            "request_id": request_id,
            "repository_name": repository_name,
            "task_type": task_type,
            "payload": payload
        },
        key=f"{repository_name}-{task_type}"
    )
    logger.info(f" Published LLM request {request_id} for {task_type}")

# --- Fonction existante : aplatir l'arborescence ---
def _flatten_repository_tree(node: dict) -> list[str]:
    """
    Aplatit l'arborescence du repository
    """
    if node['type'] == 'file':
        return [node['path']]
    elif node['type'] == 'directory':
        files = []
        for child in node['children']:
            child_files = _flatten_repository_tree(child)
            files.extend(child_files)
        return files

# ---  MODIFIÉ : Détecter les manifests avec Kafka ---
async def _detect_manifest_files(
    flattened_repository_files: list[str],
    repository_name: str
) -> list[dict[str, Any]]:
    """
    Demande au LLM Service de détecter les manifests.
    Envoie les fichiers en lots pour éviter les surcharges.
    """
    batch_size: int = 20
    
    #  Publier une requête LLM via Kafka pour chaque lot
    # Pour l'instant, on garde l'appel direct pour rester fonctionnel
    # Dans une version future, on utilisera le callback asynchrone
    
    logger.info(f" Detecting manifests for {repository_name} via LLM (direct call)")
    
    async with httpx.AsyncClient(timeout=None) as client:
        tasks = [
            client.post(
                f'{services["llm-service"]["endpoint"]}/detect-manifests',
                params={'model_name': 'qwen3:8b'},
                json=flattened_repository_files[batch_index : (batch_index + batch_size)],
            )
            for batch_index in range(0, len(flattened_repository_files), batch_size)
        ]
        responses = await asyncio.gather(*tasks)

    result: list[dict[str, Any]] = []
    for response in responses:
        response.raise_for_status()
        payload = response.json()
        result.extend(payload['manifest_files'])

    return result

# ---  MODIFIÉ : Extraire les dépendances avec Kafka ---
async def _extract_dependencies(
    detected_manifest_files: list[dict[str, Any]],
    repository_name: str
) -> list[dict[str, Any]]:
    """
    Demande au LLM Service d'extraire les dépendances.
    """
    #  Publier une requête LLM via Kafka pour chaque manifest
    # Pour l'instant, on garde l'appel direct pour rester fonctionnel
    
    logger.info(f" Extracting dependencies for {repository_name} via LLM (direct call)")
    
    async with httpx.AsyncClient(timeout=None) as client:
        tasks = [
            client.post(
                f'{services["llm-service"]["endpoint"]}/extract-dependencies',
                params={'model_name': 'qwen2.5-coder:1.5b'},
                json={
                    'path': manifest_file['path'],
                    'content': manifest_file['content'],
                },
            )
            for manifest_file in detected_manifest_files
        ]
        responses = await asyncio.gather(*tasks)

    result: list[dict[str, Any]] = []
    for response in responses:
        response.raise_for_status()
        payload = response.json()
        result.append(payload['manifest_file'])

    return result

# ---  MODIFIÉ : scan_repository avec paramètre URL ---
async def scan_repository(
    repository_name: str,
    repository_url: str = None  # 🆕 Ajout du paramètre URL (optionnel)
) -> dict[str, Any]:
    """
    Scan a repository.

    1. Retrieve the repository tree from the Storage Service.
    2. Extract all repository file paths.
    3. Send the paths to the LLM Service, in batches, to detect manifests.
    4. Retrieve the content of every detected manifest from the Storage Service.
    5. Send the manifest content to the LLM Service to extract dependencies.
    6. Return the complete scan result.
    """
    logger.info(f" Scanning repository: {repository_name}")
    
    # Step 1: Retrieve the complete repository tree.
    async with httpx.AsyncClient() as client:
        repository_content = await client.get(
            f"{services["repository-storage-service"]["endpoint"]}/repositories/{repository_name}"
        )
        repository_content.raise_for_status()
        repository_content = repository_content.json()

    # Step 2: Extract all file paths.
    flattened_repository_files: list[str] = _flatten_repository_tree(repository_content)

    # Step 3: Detect manifests dynamically through the LLM Service.
    detected_manifest_files: list[dict[str, Any]] = await _detect_manifest_files(
        flattened_repository_files,
        repository_name
    )

    # Step 4: Get the content of every detected manifest from the Storage Service.
    async with httpx.AsyncClient() as client:
        tasks = [
            client.get(
                f'{services["repository-storage-service"]["endpoint"]}/repositories/{manifest["path"]}',
                params={'display_files_content': True},
            )
            for manifest in detected_manifest_files
        ]
        responses = await asyncio.gather(*tasks)

    for manifest, response in zip(detected_manifest_files, responses):
        response.raise_for_status()
        manifest['content'] = response.json()['content']

    # Step 5: Ask the LLM to extract dependencies from the manifest content.
    extracted_dependencies = await _extract_dependencies(
        detected_manifest_files,
        repository_name
    )

    # Step 6: Merge the extracted dependencies into the detected manifest files.
    for manifest, extracted in zip(detected_manifest_files, extracted_dependencies):
        manifest['dependencies'] = extracted['dependencies']

    #  Retourner un résultat structuré
    return {
        "manifests": detected_manifest_files,
        "total_dependencies": sum(
            len(m.get('dependencies', [])) for m in detected_manifest_files
        )
    }