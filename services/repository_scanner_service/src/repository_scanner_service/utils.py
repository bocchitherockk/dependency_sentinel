import asyncio
from logging import Logger

import httpx

from common.logging.global_logger import get_global_logger
from common.config import services
from common.schemas.Directory import Directory
from common.schemas.File import File
from common.schemas.ManifestFile import ManifestFile

logger: Logger = get_global_logger(__name__)

BATCH_SIZE = 50  # Number of files to send in one request to the LLM Service
logger.info(f"LLM Service batch size set to {BATCH_SIZE} files per request.")

def _flatten_repository_tree(node: Directory | File) -> list[File]:
    if isinstance(node, File):
        return [node]
    elif isinstance(node, Directory):
        files: list[File] = []
        for child in node.children:
            child_files: list[File] = _flatten_repository_tree(child)
            files.extend(child_files)
        return files

async def _detect_manifest_files(flattened_repository_files: list[File]) -> list[File]:
    """
    Ask LLM Service to detect dependency manifest files.
    Send repository files to the LLM Service in small batches.
    Sending hundreds of files in one request may be unreliable.
    """
    async with httpx.AsyncClient(timeout=None) as client:
        # TODO: Consider using a semaphore to limit the number of concurrent requests to the LLM Service
        # because for example 2000 files / 20 = 100 concurrent requests.
        total_batches = (len(flattened_repository_files) + BATCH_SIZE - 1) // BATCH_SIZE
        tasks = []
        for batch_index in range(0, len(flattened_repository_files), BATCH_SIZE):
            batch = flattened_repository_files[batch_index : (batch_index + BATCH_SIZE)]
            # params = { 'model_name': 'qwen3:8b' }
            params = { 'model_name': 'gemini-3.5-flash-lite' }
            # params = { 'model_name': 'openai/gpt-oss-120b' }
            body = [flattened_repository_file.model_dump(mode='json') for flattened_repository_file in batch]

            logger.info(f"Detecting manifest files: batch (number = {batch_index + 1}/{total_batches}) (size = {len(batch)}) (model = {params['model_name']}).")
            logger.debug(f'Batch {batch_index + 1} content: {body}')

            tasks.append(client.post(
                f'{services['llm-service']['endpoint']}/detect-manifests',
                params= params,
                json=body,
            ))
        responses = await asyncio.gather(*tasks)

    result: list[File] = []
    for response in responses:
        response.raise_for_status()
        payload = response.json()
        for manifest_file in payload:
            result.append(File(**manifest_file))

    logger.info(f'Detected {len(result)} manifest files from {len(flattened_repository_files)} repository files.')
    logger.debug(f'Detected manifest files: {[file.path for file in result]}')
    return result

async def _extract_dependencies(detected_manifest_files: list[File]) -> list[ManifestFile]:
    """
    Ask LLM Service to extract dependencies from a manifest file.
    """
    async with httpx.AsyncClient(timeout=None) as client:
        tasks = []
        for manifest_file in detected_manifest_files:
            # params = { 'model_name': 'qwen2.5-coder:1.5b' }
            # params = { 'model_name': 'qwen3:8b' }
            params = { 'model_name': 'gemini-3.5-flash-lite' }
            # params = { 'model_name': 'openai/gpt-oss-120b' }
            body = manifest_file.model_dump(mode='json')
            logger.info(f"Extracting dependencies from manifest file '{manifest_file.path}' (model = {params['model_name']}).")
            logger.debug(f'Manifest file: {body}')

            tasks.append(client.post(
                f'{services['llm-service']['endpoint']}/extract-dependencies',
                params= params,
                json=body,
            ))
        responses = await asyncio.gather(*tasks)

    result: list[ManifestFile] = []
    for response in responses:
        response.raise_for_status()
        manifest_file_payload = response.json()
        if manifest_file_payload is None:
            logger.warning(f"LLM Service returned None for a manifest file. This may indicate an error in dependency extraction.")
            continue
        result.append(ManifestFile(**manifest_file_payload))
    logger.info(f'Extracted dependencies from {len(result)} manifest files.')
    logger.debug(f'Extracted dependencies: {result}')
    return result

async def scan_repository(repository_name: str) -> list[ManifestFile]:
    """
    Scan a repository.

    1. Retrieve the repository tree from the Storage Service.
    2. Extract all repository file paths.
    3. Send the paths to the LLM Service, in batches, to detect manifests.
    4. Retrieve the content of every detected manifest from the Storage Service.
    5. Send the manifest content to the LLM Service to extract dependencies.
    6. Return the complete scan result.
    """
    # Step 1:
    # Retrieve the complete repository tree.
    async with httpx.AsyncClient() as client:
        result = await client.get(
            f"{services['repository-storage-service']['endpoint']}/repositories/{repository_name}"
        )
        result.raise_for_status()
        repository_content: Directory = Directory(**result.json())
        logger.info(f"Retrieved repository tree for '{repository_name}' from Storage Service.")
        logger.debug(f'Repository tree content: {repository_content}')

    # Step 2:
    # Extract all file paths.
    flattened_repository_files: list[File] = _flatten_repository_tree(repository_content)
    logger.info(f"Flattened repository tree for '{repository_name}' into {len(flattened_repository_files)} files.")
    logger.debug(f'Flattened repository files: {flattened_repository_files}')

    # Step 3:
    # Detect manifests dynamically through the LLM Service.
    detected_manifest_files: list[File] = await _detect_manifest_files(flattened_repository_files)

    # Step 4:
    # Get the content of every detected manifest from the Storage Service.
    async with httpx.AsyncClient() as client:
        tasks = []
        for manifest in detected_manifest_files:
            tasks.append(client.get(
                f'{services['repository-storage-service']['endpoint']}/repositories/{manifest.path}',
                params={ 'display_files_content': True },
            ))
        responses = await asyncio.gather(*tasks)
        logger.info(f'Retrieved content for {len(detected_manifest_files)} detected manifest files from Storage Service.')

    for manifest, response in zip(detected_manifest_files, responses):
        response.raise_for_status()
        payload = response.json()
        manifest.content = payload['content']
        logger.info(f'Retrieved content for manifest file: {manifest.path}')
        logger.debug(f'Manifest file content: {manifest.content}')

    # Step 5:
    # Ask the LLM to extract dependencies from the manifest content.
    manifest_files: list[ManifestFile] = await _extract_dependencies(detected_manifest_files)

    return manifest_files
