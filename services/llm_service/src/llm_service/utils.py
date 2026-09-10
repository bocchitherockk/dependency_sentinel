import asyncio
from logging import Logger

from common.logging.global_logger import get_global_logger
from common.schemas.File import File
from common.schemas.ManifestFile import ManifestFile

from llm_service.llm_selector import LLMSelector
from llm_service.llm_clients.llm_client import LLMClient


logger: Logger = get_global_logger(__name__)

BATCH_SIZE = 50  # Number of files to send in one request to the LLM Service
logger.info(f"LLM Service batch size set to {BATCH_SIZE} files per request.")


async def detect_manifest_files(retrieved_repository_files_list: list[File]) -> list[File]:
    llm_model: str = 'gemini-3.5-flash-lite'
    model: LLMClient = LLMSelector.get_llm_model('gemini-3.5-flash-lite')

    total_batches = (len(retrieved_repository_files_list) + BATCH_SIZE - 1) // BATCH_SIZE
    tasks = []
    for batch_index in range(0, len(retrieved_repository_files_list), BATCH_SIZE):
        batch: list[File] = retrieved_repository_files_list[batch_index : (batch_index + BATCH_SIZE)]

        # TODO: there is a small unharmful bug here, the batch index is not literally the batch index, it is the file index, so the logging message is incorrect
        logger.info(f"Detecting manifest files: batch (number = {batch_index + 1}/{total_batches}) (size = {len(batch)}) (model = {llm_model}).")
        logger.debug(f'Batch {batch_index + 1} content: {[file.model_dump_json(indent=2) for file in batch]}')

        tasks.append(model.detect_manifests(batch))
    detected_manifest_files_batches: list[list[File]] = await asyncio.gather(*tasks)

    result: list[File] = [
        detected_manifest_file
        for detected_manifest_files_batch in detected_manifest_files_batches
        for detected_manifest_file in detected_manifest_files_batch
    ]

    logger.info(f'Detected {len(result)} manifest files from {len(retrieved_repository_files_list)} repository files.')
    logger.debug(f'Detected manifest files: {[file.path for file in result]}')
    return result

async def extract_dependencies(detected_manifest_files: list[File]) -> list[ManifestFile]:
    llm_model: str = 'gemini-3.5-flash-lite'
    model: LLMClient = LLMSelector.get_llm_model(llm_model)

    tasks = []
    for manifest_file in detected_manifest_files:
        logger.info(f"Extracting dependencies from manifest file '{manifest_file.path}' (model = {llm_model}).")
        logger.debug(f'Manifest file: {manifest_file.model_dump_json(indent=2)}')
        tasks.append(model.extract_dependencies(manifest_file))

    manifest_files: list[ManifestFile] = await asyncio.gather(*tasks)

    logger.info(f'Extracted dependencies from {len(manifest_files)} manifest files.')
    logger.debug(f'Extracted dependencies: {[manifest_file.model_dump_json(indent=2) for manifest_file in manifest_files]}')
    return manifest_files
