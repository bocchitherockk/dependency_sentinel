import logging
import httpx
from datetime import datetime
from common.config import services
from common.schemas.ManifestFileUpdateContext import ManifestFileUpdateContext

logger = logging.getLogger(__name__)

async def process_security_intelligence(
    repository_name: str,
    manifest_files_update_context: list[ManifestFileUpdateContext]
) -> dict:
    """
    Orchestre l'analyse d'intelligence de sécurité :
    Pour chaque ManifestFileUpdateContext reçu via Kafka :
      1. Appeler llm-service /get-update-plan → l'IA décide des versions à garder.
      2. Si le plan est VIDE → stop (pas de branche, pas de modif).
      3. Si le plan n'est PAS vide :
         a. Créer une nouvelle branche Git via repository-storage-service
         b. Appeler llm-service /update-manifest pour que le LLM réécrive le fichier
    """
    results = []

    async with httpx.AsyncClient(timeout=60.0) as client:
        for context in manifest_files_update_context:
            context_dict = context.model_dump(mode="json") if hasattr(context, "model_dump") else context

            item_result = {
                "manifest_context":      context_dict,
                "update_plan":           None,
                "branch_created":        None,
                "manifest_updated":      False,
            }

            # ─────────────────────────────────────────────────────────────────
            # Étape 1 : Appeler llm-service /get-update-plan
            # → L'IA analyse les 3 versions + failles et DÉCIDE quelle version
            #   garder pour chaque dépendance (avec reasoning)
            # ─────────────────────────────────────────────────────────────────
            try:
                update_plan_endpoint = f"{services['llm-service']['endpoint']}/get-update-plan"
                plan_response = await client.post(update_plan_endpoint, json=context_dict)
                if plan_response.status_code == 200:
                    update_plan = plan_response.json()
                else:
                    logger.warning(f"get-update-plan a retourné {plan_response.status_code}. Plan vide utilisé.")
                    update_plan = {"dependency_updates": [], "dev_dependency_updates": []}
            except Exception as error:
                logger.warning(f"Impossible d'appeler get-update-plan: {error}.")
                update_plan = {"dependency_updates": [], "dev_dependency_updates": []}

            item_result["update_plan"] = update_plan

            # ─────────────────────────────────────────────────────────────────
            # Étape 2 : Vérifier si le plan est VIDE
            # → Si vide : aucune mise à jour nécessaire, on s'arrête ici.
            #   Pas de création de branche, pas de modification de fichiers.
            # ─────────────────────────────────────────────────────────────────
            has_updates = (
                len(update_plan.get("dependency_updates", [])) > 0 or
                len(update_plan.get("dev_dependency_updates", [])) > 0
            )

            if not has_updates:
                logger.info(f"Plan VIDE pour {repository_name} ({context_dict.get('path', '?')}). Aucune action nécessaire.")
                results.append(item_result)
                continue

            # ─────────────────────────────────────────────────────────────────
            # Étape 3a : Créer une nouvelle branche Git
            # → On crée une branche isolée pour ne pas toucher à "main"
            #   Ex: "dependency-sentinel/update-2024-08-15T16:30:00"
            # ─────────────────────────────────────────────────────────────────
            timestamp = datetime.utcnow().strftime("%Y-%m-%dT%H-%M-%S")
            branch_name = f"dependency-sentinel/update-{timestamp}"

            try:
                create_branch_endpoint = f"{services['repository-storage-service']['endpoint']}/create_branch"
                branch_payload = {
                    "repository_name": repository_name,
                    "branch_name":     branch_name,
                }
                branch_resp = await client.post(create_branch_endpoint, json=branch_payload)
                if branch_resp.status_code == 200:
                    logger.info(f"Branche '{branch_name}' créée pour {repository_name}.")
                    item_result["branch_created"] = branch_name
                else:
                    logger.warning(f"Impossible de créer la branche : {branch_resp.status_code}. On continue quand même.")
                    item_result["branch_created"] = branch_name
            except Exception as error:
                logger.warning(f"Erreur lors de la création de la branche: {error}. On continue quand même.")
                item_result["branch_created"] = branch_name

            # ─────────────────────────────────────────────────────────────────
            # Étape 3b : Appeler llm-service /update-manifest
            # → On envoie au LLM :
            #     - Le fichier manifeste original (ex: package.json)
            #     - Le plan de mise à jour (la décision de l'IA)
            # → Le LLM réécrit le contenu du fichier avec les bonnes versions
            # ─────────────────────────────────────────────────────────────────
            manifest_file = {
                "path": context_dict.get("path", ""),
                "name": context_dict.get("path", "").split("/")[-1],
                "content": context_dict.get("content", ""),
            }
            update_manifest_payload = {
                "manifest_file": manifest_file,
                "update_plan":   update_plan,
            }

            try:
                update_manifest_endpoint = f"{services['llm-service']['endpoint']}/update-manifest"
                manifest_resp = await client.post(update_manifest_endpoint, json=update_manifest_payload)
                if manifest_resp.status_code == 200:
                    logger.info(f"Fichier manifest mis à jour par le LLM pour {repository_name}.")
                    item_result["manifest_updated"] = True
                    item_result["updated_manifest"] = manifest_resp.json()
                else:
                    logger.warning(f"update-manifest a retourné {manifest_resp.status_code} pour {repository_name}.")
            except Exception as error:
                logger.warning(f"Impossible d'appeler update-manifest: {error}.")

            results.append(item_result)

    return {
        "repository_name": repository_name,
        "processed_count": len(results),
        "details":         results
    }
