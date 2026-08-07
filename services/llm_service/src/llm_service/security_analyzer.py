from typing import Dict, Any, List
import json

class SecurityLLMAnalyzer:
    """
    Service LLM (Agentic RAG) pour l'analyse décisionnelle de sécurité.
    Le LLM analyse la comparaison entre versions et vulnérabilités pour décider
    si le développeur doit MIGRER vers la nouvelle version ou non.
    """

    @staticmethod
    async def analyze_delta(delta_dict: Dict[str, Any]) -> Dict[str, Any]:
        """
        Interroge le LLM pour comparer les versions et décider s'il faut migrer.
        """
        package_name = delta_dict.get("package_name", "dépendance")
        current_version = delta_dict.get("current_version", "inconnue")
        candidate_version = delta_dict.get("candidate_version", "inconnue")
        resolved_count = delta_dict.get("resolved_cves_count", 0)
        remaining_vulns = delta_dict.get("remaining_vulnerabilities", [])
        new_vulns = delta_dict.get("new_vulnerabilities", [])

        has_high_new = any(v.get("severity") in ["HIGH", "CRITICAL"] for v in new_vulns)
        has_high_remaining = any(v.get("severity") in ["HIGH", "CRITICAL"] for v in remaining_vulns)

        system_instructions = (
            "Tu es un expert en cybersécurité et architecture logicielle. "
            "Ton rôle est d'analyser la comparaison entre la version actuelle d'une dépendance et la nouvelle version candidate. "
            "Tu dois décider si le développeur doit MIGRER vers la nouvelle version ou NON, et rédiger une explication claire et précise."
        )

        prompt = (
            f"Analyse de migration pour le package : {package_name}\n"
            f"- Version actuelle : {current_version}\n"
            f"- Nouvelle version candidate : {candidate_version}\n"
            f"- Failles de sécurité résolues par la migration : {resolved_count}\n"
            f"- Nouvelles failles introduites par la migration : {len(new_vulns)}\n"
            f"- Failles restantes dans la nouvelle version : {len(remaining_vulns)}\n\n"
            f"Consignes de décision :\n"
            f"1. Si la migration résout des vulnérabilités sans en introduire de nouvelles hautement critiques, recommande de MIGRER ('FAVORABLE').\n"
            f"2. Si la migration introduit de nouvelles failles graves, déconseille la migration ('DISCOURAGED').\n"
            f"3. Si la migration résout des failles mais que d'autres failles subsistent, recommande de MIGRER AVEC PRUDENCE ('CAUTIOUS').\n\n"
            f"Retourne un objet JSON valide contenant :\n"
            f"- 'recommendation': 'FAVORABLE', 'CAUTIOUS' ou 'DISCOURAGED'\n"
            f"- 'rationale': Ton explication détaillée indiquant explicitement si le développeur doit migrer vers {candidate_version} ou conserver {current_version}."
        )

        try:
            from llm_service.llm_selector import LLMSelector
            client = LLMSelector.get_llm_model("qwen2.5-coder:1.5b")
            llm_response = await client.chat(
                system_instructions=system_instructions,
                prompt=prompt,
                response_format={"type": "json_object"}
            )

            if isinstance(llm_response, str):
                llm_response = json.loads(llm_response)

            if isinstance(llm_response, dict) and "recommendation" in llm_response and "rationale" in llm_response:
                return {
                    "recommendation": llm_response["recommendation"],
                    "rationale": llm_response["rationale"]
                }
        except Exception:
            pass

        # Fallback analytique déterministe si LLM hors-ligne
        if has_high_new:
            recommendation = "DISCOURAGED"
            rationale = (
                f"Ne pas migrer : La migration de la version {current_version} vers {candidate_version} est déconseillée "
                f"car elle introduit {len(new_vulns)} nouvelle(s) vulnérabilité(s) critiques."
            )
        elif resolved_count > 0 and not has_high_remaining:
            recommendation = "FAVORABLE"
            rationale = (
                f"Migration recommandée : Vous devez migrer de la version {current_version} vers {candidate_version}. "
                f"Cette migration permet de corriger {resolved_count} vulnérabilité(s) de sécurité connue(s)."
            )
        elif resolved_count > 0 and has_high_remaining:
            recommendation = "CAUTIOUS"
            rationale = (
                f"Migration à effectuer avec prudence : Il est recommandé de migrer vers {candidate_version} "
                f"pour corriger {resolved_count} faille(s), mais attention : {len(remaining_vulns)} faille(s) subsiste(nt) encore."
            )
        elif candidate_version != current_version:
            recommendation = "FAVORABLE"
            rationale = (
                f"Migration conseillée : Il est recommandé de migrer de {current_version} vers {candidate_version} "
                f"pour bénéficier des dernières améliorations de stabilité et corrections de bugs."
            )
        else:
            recommendation = "FAVORABLE"
            rationale = f"Aucune migration nécessaire : La dépendance est déjà sur la version la plus récente ({current_version})."

        return {
            "recommendation": recommendation,
            "rationale": rationale
        }
