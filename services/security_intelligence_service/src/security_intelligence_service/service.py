import asyncio
from datetime import datetime, timezone

import httpx

from common.config import services
from common.schemas.File import File
from common.schemas.DependencyUpdateContext import DependencyUpdateContext
from common.schemas.ManifestFileUpdateContext import ManifestFileUpdateContext
from common.schemas.DependencyUpdatePlan import DependencyUpdatePlan
from common.schemas.ManifestFileUpdatePlan import ManifestFileUpdatePlan
from common.schemas.CreateBranchRequest import CreateBranchRequest
from common.schemas.UpdateManifestRequest import UpdateManifestRequest


async def get_dependency_update_plan(dependency_update_context: DependencyUpdateContext) -> DependencyUpdatePlan:
    async with httpx.AsyncClient(timeout=None) as client:
        response = await client.post(
            f"{services['llm-service']['endpoint']}/get-update-plan",
            json=dependency_update_context.model_dump(mode='json'),
        )
    response.raise_for_status()
    return DependencyUpdatePlan(**response.json())

async def get_dependencies_update_plan(dependencies_update_context: list[DependencyUpdateContext]) -> list[DependencyUpdatePlan]:
    tasks = [
        get_dependency_update_plan(context)
        for context in dependencies_update_context
    ]
    return await asyncio.gather(*tasks)

async def get_manifest_file_update_plan(manifest_file_update_context: ManifestFileUpdateContext) -> ManifestFileUpdatePlan:
    dependencies_update_plans, dev_dependencies_update_plans = await asyncio.gather(
        get_dependencies_update_plan(manifest_file_update_context.dependencies_update_context),
        get_dependencies_update_plan(manifest_file_update_context.dev_dependencies_update_context)
    )

    return ManifestFileUpdatePlan(
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
    return response.text

async def analyze_update_context_and_update_manifests(
    repository_name: str,
    manifest_files_update_context: list[ManifestFileUpdateContext]
) -> str:
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
    manifest_files_update_plans: list[ManifestFileUpdatePlan] = await asyncio.gather(*[
        get_manifest_file_update_plan(manifest_file_update_context)
        for manifest_file_update_context in manifest_files_update_context
    ])

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
        return ''

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

    return summary
