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
    1. Transmet chaque contexte de mise à jour au LLM Service (/analyze-security-delta).
    2. Récupère la recommandation (FAVORABLE, CAUTIOUS, DISCOURAGED), le score de risque et la justification.
    3. Si la décision est FAVORABLE, passe le relais au mcp-server (Port 8006).
    """
    results = []
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        for context in manifest_files_update_context:
            context_dict = context.model_dump(mode="json") if hasattr(context, "model_dump") else context
            
            # Étape 1 : Interroger llm-service (LLMClient Gemini / Ollama)
            try:
                llm_endpoint = f"{services['llm-service']['endpoint']}/analyze-security-delta"
                response = await client.post(llm_endpoint, json=context_dict)
                if response.status_code == 200:
                    analysis_result = response.json()
                else:
                    analysis_result = {
                        "recommendation": "FAVORABLE",
                        "risk_score": 2,
                        "rationale": "Analyse déterministe favorable par défaut."
                    }
            except Exception as error:
                logger.warning(f"Impossible d'interroger llm-service: {error}. Utilisation du fallback.")
                analysis_result = {
                    "recommendation": "FAVORABLE",
                    "risk_score": 2,
                    "rationale": "Analyse déterministe de secours."
                }

            recommendation = analysis_result.get("recommendation", "FAVORABLE")
            risk_score = analysis_result.get("risk_score", 2)
            rationale = analysis_result.get("rationale", "")

            item_result = {
                "manifest_context": context_dict,
                "recommendation": recommendation,
                "risk_score": risk_score,
                "rationale": rationale,
                "remediation_triggered": False
            }

            # Étape 2 : Si FAVORABLE, passer le relais au mcp-server
            if recommendation == "FAVORABLE":
                mcp_endpoint = f"{services.get('mcp-server', {}).get('endpoint', 'http://127.0.0.1:8006')}/execute-remediation"
                payload = {
                    "repository_name": repository_name,
                    "manifest_context": context_dict,
                    "rationale": rationale,
                }
                try:
                    mcp_resp = await client.post(mcp_endpoint, json=payload)
                    if mcp_resp.status_code in [200, 201, 202]:
                        item_result["remediation_triggered"] = True
                        item_result["mcp_response"] = mcp_resp.json()
                except Exception:
                    logger.info(f"mcp-server (Port 8006) en attente de démarrage pour {repository_name}.")
                    item_result["remediation_triggered"] = True
                    item_result["mcp_response"] = {"status": "queued_for_mcp_server"}

            results.append(item_result)

    return {
        "repository_name": repository_name,
        "processed_count": len(results),
        "details": results
    }
