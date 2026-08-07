import logging
import httpx
from datetime import datetime, timezone
from typing import Any, List, Dict

from common.config import services
from common.registry_adapters.factory import RegistryAdapterFactory
from common.security.osv_checker import OSVChecker
from common.schemas.DependencySecurityReport import DependencySecurityReport, DependencySecurityDelta

logger = logging.getLogger(__name__)

async def process_registry_and_security(repository_name: str, detected_manifest_files: List[Any]) -> DependencySecurityReport:
    """
    Orchestre la résolution des versions via RegistryAdapterFactory (Libraries.io),
    l'analyse différentielle des failles via OSVChecker, et l'explication décisionnelle via LLM Service.
    """
    total_dependencies = 0
    up_to_date_count = 0
    updates_available_count = 0
    resolved_cves_total = 0
    deltas: List[DependencySecurityDelta] = []

    async with httpx.AsyncClient(timeout=60.0) as http_client:
        for manifest in detected_manifest_files:
            if hasattr(manifest, "dependencies"):
                dependencies = manifest.dependencies or []
            elif isinstance(manifest, dict):
                dependencies = manifest.get("dependencies", [])
            else:
                dependencies = []

            for dep in dependencies:
                total_dependencies += 1
                if hasattr(dep, "name"):
                    pkg_name = dep.name
                    curr_ver = dep.version or "1.0.0"
                    reg_obj = dep.registry
                    registry_name = reg_obj.name if hasattr(reg_obj, "name") else "pypi"
                elif isinstance(dep, dict):
                    pkg_name = dep.get("name")
                    curr_ver = dep.get("version", "1.0.0")
                    reg_info = dep.get("registry", {})
                    registry_name = reg_info.get("name", "pypi") if isinstance(reg_info, dict) else "pypi"
                else:
                    continue

                if not pkg_name:
                    continue

                # 1. Résolution de la dernière version via RegistryAdapterFactory (Libraries.io)
                adapter = RegistryAdapterFactory.get_adapter(registry_name)
                reg_result = await adapter.get_latest_version(pkg_name)
                latest_ver = reg_result.get("latest_version") or curr_ver
                license_name = reg_result.get("license") or "Non spécifiée"

                if latest_ver == curr_ver:
                    up_to_date_count += 1
                else:
                    updates_available_count += 1

                # 2. Analyse différentielle des vulnérabilités CVE via Google OSV.dev
                osv_checker = OSVChecker()
                osv_result = await osv_checker.analyze_differential(
                    package_name=pkg_name,
                    current_version=curr_ver,
                    candidate_version=latest_ver,
                    ecosystem=registry_name
                )

                resolved_count = osv_result.get("resolved_cves_count", 0)
                resolved_cves_total += resolved_count

                # 3. Interrogation du Service LLM pour la décision et l'explication
                delta_payload = {
                    "package_name": pkg_name,
                    "registry": registry_name,
                    "current_version": curr_ver,
                    "candidate_version": latest_ver,
                    "resolved_cves_count": resolved_count,
                    "resolved_vulnerabilities": osv_result.get("resolved_vulnerabilities", []),
                    "remaining_vulnerabilities": osv_result.get("remaining_vulnerabilities", []),
                    "new_vulnerabilities": osv_result.get("new_vulnerabilities", []),
                }

                recommendation = "FAVORABLE"
                rationale = "Mise à jour recommandée."
                try:
                    llm_url = f"{services['llm-service']['endpoint']}/analyze-security-delta"
                    resp = await http_client.post(llm_url, json=delta_payload)
                    if resp.status_code == 200:
                        llm_data = resp.json()
                        recommendation = llm_data.get("recommendation", recommendation)
                        rationale = llm_data.get("rationale", rationale)
                except Exception as e:
                    logger.warning(f"Impossible d'interroger le service LLM pour {pkg_name}: {e}")

                delta_obj = DependencySecurityDelta(
                    package_name=pkg_name,
                    registry=registry_name,
                    current_version=curr_ver,
                    latest_version=latest_ver,
                    current_vulnerabilities_count=len(osv_result.get("current_vulnerabilities", [])),
                    candidate_vulnerabilities_count=len(osv_result.get("candidate_vulnerabilities", [])),
                    resolved_cves_count=resolved_count,
                    resolved_vulnerabilities=osv_result.get("resolved_vulnerabilities", []),
                    remaining_vulnerabilities=osv_result.get("remaining_vulnerabilities", []),
                    new_vulnerabilities=osv_result.get("new_vulnerabilities", []),
                    license=license_name,
                    recommendation=recommendation,
                    rationale=rationale
                )
                deltas.append(delta_obj)

    # Détermination de la recommandation globale
    has_discouraged = any(d.recommendation == "DISCOURAGED" for d in deltas)
    has_cautious = any(d.recommendation == "CAUTIOUS" for d in deltas)
    if has_discouraged:
        overall = "DISCOURAGED"
        summary = "Attention : Certaines mises à jour introduisent des vulnérabilités critiques. Examinez les dépendances déconseillées."
    elif has_cautious:
        overall = "CAUTIOUS"
        summary = "Mise à jour recommandée avec prudence : Plusieurs vulnérabilités sont résolues mais des failles subsistent."
    else:
        overall = "FAVORABLE"
        summary = "Le projet présente un profil de mise à jour très favorable. Les dépendances peuvent être mises à jour en toute sécurité."

    report = DependencySecurityReport(
        repository_name=repository_name,
        scanned_at=datetime.now(timezone.utc).isoformat(),
        total_dependencies=total_dependencies,
        up_to_date_count=up_to_date_count,
        updates_available_count=updates_available_count,
        resolved_cves_total=resolved_cves_total,
        overall_recommendation=overall,
        executive_summary=summary,
        dependency_deltas=deltas
    )

    return report
