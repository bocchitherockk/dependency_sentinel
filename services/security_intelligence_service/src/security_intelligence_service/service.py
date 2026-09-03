import asyncio
from datetime import datetime, timezone
from logging import Logger

import httpx

from common.logging.global_logger import get_global_logger
from common.config import services
from common.schemas.File import File
from common.schemas.DependencyUpdateContext import DependencyUpdateContext
from common.schemas.ManifestFileUpdateContext import ManifestFileUpdateContext
from common.schemas.DependencyUpdatePlan import DependencyUpdatePlan
from common.schemas.ManifestFileUpdatePlan import ManifestFileUpdatePlan
from common.schemas.CreateBranchRequest import CreateBranchRequest
from common.schemas.UpdateManifestRequest import UpdateManifestRequest


logger: Logger = get_global_logger(__name__)

async def get_dependency_update_plan(dependency_update_context: DependencyUpdateContext) -> DependencyUpdatePlan:
    try:
        async with httpx.AsyncClient(timeout=None) as client:
            response = await client.post(
                f"{services['llm-service']['endpoint']}/get-update-plan",
                params={'model_name': 'gemini-3.5-flash-lite'},
                json=dependency_update_context.model_dump(mode='json'),
            )
        response.raise_for_status()
        result: DependencyUpdatePlan = DependencyUpdatePlan(**response.json())
        logger.info(f"DependencyUpdatePlan generated for dependency '{dependency_update_context.current_version_dependency_report.name}' with current version '{dependency_update_context.current_version_dependency_report.version}' in registry '{dependency_update_context.current_version_dependency_report.registry_name}'.")
        logger.debug(f'DependencyUpdatePlan details: {result}')
        return result
    except Exception as e:
        logger.error(f"Failed to get update plan for dependency '{dependency_update_context.current_version_dependency_report.name}': {e}. Skipping it.")
        return DependencyUpdatePlan(
            dependency_name=dependency_update_context.current_version_dependency_report.name,
            current_version=dependency_update_context.current_version_dependency_report.version,
            recommended_version=dependency_update_context.current_version_dependency_report.version,
            reasoning=f"Error occurred during LLM processing: {e}"
        )

async def get_dependencies_update_plan(dependencies_update_context: list[DependencyUpdateContext]) -> list[DependencyUpdatePlan]:
    result: list[DependencyUpdatePlan] = []
    for context in dependencies_update_context:
        plan = await get_dependency_update_plan(context)
        result.append(plan)
        await asyncio.sleep(5)  # Eviter la limite Gemini de 15 requêtes/minute
        
    logger.info(f"DependenciesUpdatePlan generated for {len(result)} dependencies.")
    logger.debug(f'DependenciesUpdatePlan details: {result}')
    return result

async def get_manifest_file_update_plan(manifest_file_update_context: ManifestFileUpdateContext) -> ManifestFileUpdatePlan:
    dependencies_update_plans = await get_dependencies_update_plan(manifest_file_update_context.dependencies_update_context)
    dev_dependencies_update_plans = await get_dependencies_update_plan(manifest_file_update_context.dev_dependencies_update_context)

    result: ManifestFileUpdatePlan = ManifestFileUpdatePlan(
        manifest_file_path=manifest_file_update_context.manifest_file_path,
        dependencies_updates=[
            dependency_update_plan
            for dependency_update_plan in dependencies_update_plans
            if dependency_update_plan.current_version != dependency_update_plan.recommended_version
        ],
        dev_dependencies_updates=[
            dev_dependency_update_plan
            for dev_dependency_update_plan in dev_dependencies_update_plans
            if dev_dependency_update_plan.current_version != dev_dependency_update_plan.recommended_version
        ],
    )
    logger.info(f"ManifestFileUpdatePlan generated for manifest file '{manifest_file_update_context.manifest_file_path}'.")
    logger.debug(f'ManifestFileUpdatePlan details: {result}')
    return result

async def create_git_branch(repository_name: str, branch_name: str) -> None:
    async with httpx.AsyncClient() as client:
        create_branch_request: CreateBranchRequest = CreateBranchRequest(
            branch_name=branch_name,
            repository_name=repository_name,
        )
        response = await client.post(
            f"{services['repository-storage-service']['endpoint']}/create_branch",
            json=create_branch_request.model_dump(mode='json')
        )

    response.raise_for_status()
    logger.info(f"Git branch '{branch_name}' created for repository '{repository_name}'.")

async def get_manifest_files(manifest_files_update_plans: list[ManifestFileUpdatePlan]) -> list[File]:
    async with httpx.AsyncClient() as client:
        responses = await asyncio.gather(*[
            client.get(
                f"{services['repository-storage-service']['endpoint']}/repositories/{manifest_file_update_plan.manifest_file_path}",
                params={ 'display_files_content': True }
            )
            for manifest_file_update_plan in manifest_files_update_plans
        ])

    manifest_files: list[File] = []
    for response in responses:
        response.raise_for_status()
        manifest_files.append(File(**response.json()))

    logger.info(f"Retrieved manifest files for {len(manifest_files)} manifest files with content.")
    logger.debug(f'Retrieved manifest files details: {manifest_files}')
    return manifest_files

async def update_manifest_file(manifest_file: File, update_plan: ManifestFileUpdatePlan) -> str:
    update_manifest_request: UpdateManifestRequest = UpdateManifestRequest(
        manifest_file=manifest_file,
        update_plan=update_plan,
    )
    async with httpx.AsyncClient(timeout=None) as client:
        response = await client.post(
            f"{services['llm-service']['endpoint']}/update-manifest",
            params={ 'model_name': 'gemini-3.5-flash-lite' },
            json=update_manifest_request.model_dump(mode='json'),
        )

    response.raise_for_status()
    logger.info(f"Manifest file '{manifest_file.path}' updated with LLM service.")
    logger.debug(f"Update reasoning for '{manifest_file.path}': {response.text}")
    return response.text

async def analyze_update_context_and_update_manifests(
    repository_name: str,
    manifest_files_update_context: list[ManifestFileUpdateContext]
) -> tuple[str, str] | tuple[None, None]:
    """
    Orchestre l'analyse d'intelligence de sécurité :
    Pour chaque ManifestFileUpdateContext reçu via Kafka :
        1. Appeler llm-service /get-update-plan → l'IA décide des versions à garder.
        2. Si le plan est VIDE → stop (pas de branche, pas de modif).
        3. Si le plan n'est PAS vide :
            a. Créer une nouvelle branche Git via repository-storage-service
            b. Appeler llm-service /update-manifest pour que le LLM réécrive le fichier
    """
    # ─────────────────────────────────────────────────────────────────
    # Étape 1 : Appeler llm-service /get-update-plan
    # → L'IA analyse les 3 versions + failles et DÉCIDE quelle version
    #   garder pour chaque dépendance (avec reasoning)
    # ─────────────────────────────────────────────────────────────────
    manifest_files_update_plans: list[ManifestFileUpdatePlan] = []
    for manifest_file_update_context in manifest_files_update_context:
        plan = await get_manifest_file_update_plan(manifest_file_update_context)
        manifest_files_update_plans.append(plan)

    # Clean up the update plans to remove any dependencies that don't actually need updates
    for manifest_file_update_plan in manifest_files_update_plans:
        manifest_file_update_plan.remove_unnecessary_update_elements()

    # Remove any manifest files that have no updates after cleaning
    manifest_files_update_plans = [
        manifest_file_update_plan
        for manifest_file_update_plan in manifest_files_update_plans
        if manifest_file_update_plan.has_updates()
    ]

    # ─────────────────────────────────────────────────────────────────
    # Étape 2 : Vérifier si le plan est VIDE
    # → Si vide : aucune mise à jour nécessaire, on s'arrête ici.
    #   Pas de création de branche, pas de modification de fichiers.
    # ─────────────────────────────────────────────────────────────────
    if not manifest_files_update_plans:
        logger.info(f"No updates needed for repository '{repository_name}'. No branch created, no files modified.")
        return None, None
    logger.info(f"Updates needed for repository '{repository_name}'. Proceeding to create a new branch and update manifest files.")
    logger.debug(f'ManifestFileUpdatePlans details: {manifest_files_update_plans}')

    # ─────────────────────────────────────────────────────────────────
    # Étape 3 : Créer une nouvelle branche Git
    # → On crée une branche isolée pour ne pas toucher à "main"
    #   Ex: "dependency-sentinel/update-2024-08-15T16:30:00"
    # ─────────────────────────────────────────────────────────────────
    timestamp: str = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H-%M-%S')
    branch_name: str = f'dependency-sentinel/update-{timestamp}'
    await create_git_branch(repository_name, branch_name)

    # Step 4: gather the files to update and call the LLM service to update them
    manifest_files_to_update: list[File] = await get_manifest_files(manifest_files_update_plans)

    # ─────────────────────────────────────────────────────────────────
    # Étape 5 : Appeler llm-service /update-manifest
    # → On envoie au LLM :
    #     - Le fichier manifeste original (ex: package.json)
    #     - Le plan de mise à jour (la décision de l'IA)
    # → Le LLM réécrit le contenu du fichier avec les bonnes versions
    # ─────────────────────────────────────────────────────────────────
    summaries: list[str] = await asyncio.gather(*[
        update_manifest_file(manifest_file, manifest_file_update_plan)
        for manifest_file, manifest_file_update_plan in zip(manifest_files_to_update, manifest_files_update_plans)
    ])
    
    summary: str = ''
    for manifest_file_update_plan, reasoning in zip(manifest_files_update_plans, summaries):
        summary += f"###### file: {manifest_file_update_plan.manifest_file_path} ######\n"
        summary += f"Reasoning:\n{reasoning}\n"
        summary += "───────────────────────────────────────────\n"

    logger.info(f"Manifest files updated for repository '{repository_name}' on branch '{branch_name}'.")
    logger.debug(f'Update summary as PR body for repository {repository_name}:\n{summary}')
    return branch_name, summary
