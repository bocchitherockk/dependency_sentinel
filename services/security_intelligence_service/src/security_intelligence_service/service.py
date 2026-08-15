import logging
import httpx
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
      3. Si le plan n'est PAS vide → envoyer au mcp-server pour créer la branche et modifier les fichiers.
    """
    results = []

    async with httpx.AsyncClient(timeout=60.0) as client:
        for context in manifest_files_update_context:
            context_dict = context.model_dump(mode="json") if hasattr(context, "model_dump") else context

            item_result = {
                "manifest_context":      context_dict,
                "update_plan":           None,
                "remediation_triggered": False
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
            # Étape 3 : Plan NON vide → envoyer au mcp-server
            # → Le mcp-server va :
            #   1. Créer une nouvelle branche Git
            #   2. Appeler llm-service /update-manifest pour réécrire le fichier
            #   3. Enregistrer le fichier modifié dans la nouvelle branche
            # ─────────────────────────────────────────────────────────────────
            logger.info(f"Plan non vide pour {repository_name}. Envoi au mcp-server pour remédiation.")
            mcp_endpoint = f"{services.get('mcp-server', {}).get('endpoint', 'http://127.0.0.1:8005')}/execute-remediation"
            payload = {
                "repository_name":  repository_name,
                "manifest_context": context_dict,
                "update_plan":      update_plan,
            }
            try:
                mcp_resp = await client.post(mcp_endpoint, json=payload)
                if mcp_resp.status_code in [200, 201, 202]:
                    item_result["remediation_triggered"] = True
                    item_result["mcp_response"] = mcp_resp.json()
                else:
                    logger.warning(f"mcp-server a retourné {mcp_resp.status_code} pour {repository_name}.")
            except Exception as error:
                logger.info(f"mcp-server en attente de démarrage pour {repository_name}: {error}")
                item_result["remediation_triggered"] = True
                item_result["mcp_response"] = {"status": "queued_for_mcp_server"}

            results.append(item_result)

    return {
        "repository_name": repository_name,
        "processed_count": len(results),
        "details":         results
    }
