import asyncio
from datetime import datetime, timezone

import httpx

from common.config import services
from common.schemas.File import File
from common.schemas.ManifestFileUpdateContext import ManifestFileUpdateContext
from common.schemas.ManifestFileUpdatePlan import ManifestFileUpdatePlan
from common.schemas.CreateBranchRequest import CreateBranchRequest
from common.schemas.UpdateManifestRequest import UpdateManifestRequest


async def process_security_intelligence(
    repository_name: str,
    manifest_files_update_context: list[ManifestFileUpdateContext]
) -> list[File]:
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
    async with httpx.AsyncClient(timeout=None) as client:
        all_manifest_files_update_plan_requests = [
            client.post(
                f"{services['llm-service']['endpoint']}/get-update-plan",
                json=manifest_file_update_context
            )
            for manifest_file_update_context in manifest_files_update_context
        ]
        all_manifest_files_update_plan: list[ManifestFileUpdatePlan] = await asyncio.gather(*all_manifest_files_update_plan_requests)

    # ─────────────────────────────────────────────────────────────────
    # Étape 2 : Vérifier si le plan est VIDE
    # → Si vide : aucune mise à jour nécessaire, on s'arrête ici.
    #   Pas de création de branche, pas de modification de fichiers.
    # ─────────────────────────────────────────────────────────────────
    manifest_files_update_plan: list[ManifestFileUpdatePlan] = [plan for plan in all_manifest_files_update_plan if plan.has_updates()]
    if not any(manifest_file_update_plan.has_updates() for manifest_file_update_plan in manifest_files_update_plan):
        return []

    # ─────────────────────────────────────────────────────────────────
    # Étape 3 : Créer une nouvelle branche Git
    # → On crée une branche isolée pour ne pas toucher à "main"
    #   Ex: "dependency-sentinel/update-2024-08-15T16:30:00"
    # ─────────────────────────────────────────────────────────────────
    timestamp: str = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H-%M-%S')
    branch_name: str = f'dependency-sentinel/update-{timestamp}'
    async with httpx.AsyncClient() as client:
        client.post(
            f"{services['repository-storage-service']['endpoint']}/create_branch",
            json=CreateBranchRequest(
                branch_name=branch_name,
                repository_name=repository_name,
            )
        )

    # Step 4: gather the files to update and call the LLM service to update them
    async with httpx.AsyncClient() as client:
        manifest_files_to_update: list[File] = asyncio.gather(*[
            client.get(
                f"{services['repository-storage-service']['endpoint']}/repositories/{manifest_file_update_plan.path}",
                params={ 'display_files_content': True }
            )
            for manifest_file_update_plan in manifest_files_update_plan
        ])

    # ─────────────────────────────────────────────────────────────────
    # Étape 5 : Appeler llm-service /update-manifest
    # → On envoie au LLM :
    #     - Le fichier manifeste original (ex: package.json)
    #     - Le plan de mise à jour (la décision de l'IA)
    # → Le LLM réécrit le contenu du fichier avec les bonnes versions
    # ─────────────────────────────────────────────────────────────────
    update_manifest_requests: list[UpdateManifestRequest] = [
        UpdateManifestRequest(
            manifest_file=manifest_file,
            update_plan=manifest_file_update_plan,
        )
        for manifest_file, manifest_file_update_plan in zip(manifest_files_to_update, manifest_files_update_plan)
    ]
    async with httpx.AsyncClient(timeout=None) as client:
        updated_manifest_files: list[File] = await asyncio.gather(*[
            client.post(
                f"{services['llm-service']['endpoint']}/update-manifest",
                json=update_manifest_request,
            )
            for update_manifest_request in update_manifest_requests
        ])

    return updated_manifest_files

    # TODO: Étape 6 : Commit et push des fichiers mis à jour sur la branche Git
