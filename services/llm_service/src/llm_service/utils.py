import asyncio
from logging import Logger

from common.logging.global_logger import get_global_logger
from common.schemas.File import File
from common.schemas.ManifestFile import ManifestFile
from common.schemas.DependencyUpdateContext import DependencyUpdateContext
from common.schemas.DependencyUpdatePlan import DependencyUpdatePlan
from common.schemas.ManifestFileUpdateContext import ManifestFileUpdateContext
from common.schemas.ManifestFileUpdatePlan import ManifestFileUpdatePlan

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
    logger.debug(f'Detected manifest files: {[str(file.path) for file in result]}')
    return result

async def extract_dependencies(detected_manifest_files: list[File]) -> list[ManifestFile]:
    llm_model: str = 'gemini-3.5-flash-lite'
    model: LLMClient = LLMSelector.get_llm_model(llm_model)

    tasks = []
    for manifest_file in detected_manifest_files:
        logger.info(f"Extracting dependencies from manifest file '{str(manifest_file.path)}' (model = {llm_model}).")
        logger.debug(f'Manifest file: {manifest_file.model_dump_json(indent=2)}')
        tasks.append(model.extract_dependencies(manifest_file))

    manifest_files: list[ManifestFile] = await asyncio.gather(*tasks)

    logger.info(f'Extracted dependencies from {len(manifest_files)} manifest files.')
    logger.debug(f'Extracted dependencies: {[manifest_file.model_dump_json(indent=2) for manifest_file in manifest_files]}')
    return manifest_files


async def get_dependency_update_plan(dependency_update_context: DependencyUpdateContext) -> DependencyUpdatePlan:
    llm_model: str = 'default'
    model: LLMClient = LLMSelector.get_llm_model(llm_model)
    dependency_update_plan: DependencyUpdatePlan = await model.get_dependency_update_plan(dependency_update_context)
    logger.info(f"DependencyUpdatePlan generated for dependency '{dependency_update_context.current_version_dependency_report.name}' with current version '{dependency_update_context.current_version_dependency_report.version}' in registry '{dependency_update_context.current_version_dependency_report.registry_name}'.")
    logger.debug(f'DependencyUpdatePlan details: {dependency_update_plan.model_dump_json(indent=2)}')
    return dependency_update_plan

async def get_dependencies_update_plan(dependencies_update_context: list[DependencyUpdateContext]) -> list[DependencyUpdatePlan]:
    tasks = [
        get_dependency_update_plan(context)
        for context in dependencies_update_context
    ]
    dependencies_update_plan: list[DependencyUpdatePlan] = await asyncio.gather(*tasks)
    logger.info(f"DependenciesUpdatePlan generated for {len(dependencies_update_plan)} dependencies.")
    logger.debug(f'DependenciesUpdatePlan details: {[dependency_update_plan.model_dump_json(indent=2) for dependency_update_plan in dependencies_update_plan]}')
    return dependencies_update_plan

async def get_manifest_file_update_plan(manifest_file_update_context: ManifestFileUpdateContext) -> ManifestFileUpdatePlan:
    dependencies_update_plan, dev_dependencies_update_plan = await asyncio.gather(
        get_dependencies_update_plan(manifest_file_update_context.dependencies_update_context),
        get_dependencies_update_plan(manifest_file_update_context.dev_dependencies_update_context)
    )

    manifest_file_update_plan: ManifestFileUpdatePlan = ManifestFileUpdatePlan(
        **manifest_file_update_context.model_dump(),
        dependencies_updates=[
            dependency_update_plan
            for dependency_update_plan in dependencies_update_plan
            if dependency_update_plan.current_version != dependency_update_plan.recommended_version
        ],
        dev_dependencies_updates=[
            dev_dependency_update_plan
            for dev_dependency_update_plan in dev_dependencies_update_plan
            if dev_dependency_update_plan.current_version != dev_dependency_update_plan.recommended_version
        ],
    )
    logger.info(f"ManifestFileUpdatePlan generated for manifest file '{manifest_file_update_context.path}'.")
    logger.debug(f'ManifestFileUpdatePlan details: {manifest_file_update_plan.model_dump_json(indent=2)}')
    return manifest_file_update_plan

async def get_manifest_files_update_plan(manifest_files_update_context: list[ManifestFileUpdateContext]) -> list[ManifestFileUpdatePlan]:
    tasks = [
        get_manifest_file_update_plan(context)
        for context in manifest_files_update_context
    ]
    manifest_files_update_plan: list[ManifestFileUpdatePlan] = await asyncio.gather(*tasks)
    logger.info(f"ManifestFilesUpdatePlan generated for {len(manifest_files_update_plan)} manifest files.")
    logger.debug(f'ManifestFilesUpdatePlan details: {[_manifest_file_update_plan.model_dump_json(indent=2) for _manifest_file_update_plan in manifest_files_update_plan]}')
    return manifest_files_update_plan

async def update_manifest_file(manifest_file_update_plan: ManifestFileUpdatePlan) -> str:
    llm_model: str = 'gemini-3.5-flash-lite'
    model: LLMClient = LLMSelector.get_llm_model(llm_model)

    update_summary: str = await model.update_manifest_file(manifest_file_update_plan)

    logger.info(f"Manifest file '{str(manifest_file_update_plan.path)}' updated with LLM service.")
    logger.debug(f"Update reasoning for '{str(manifest_file_update_plan.path)}': {update_summary}")
    return update_summary
