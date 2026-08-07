import httpx
from typing import Dict, Any, List, Optional
from pydantic import BaseModel
from common.registry_adapters.factory import RegistryAdapterFactory

class SimpleOSVReport(BaseModel):
    package_name: str
    current_version: str
    latest_version: str
    is_outdated: bool
    current_cve_count: int
    latest_cve_count: int
    recommendation_status: str
    explanation_markdown: str

class OSVChecker:
    """
    Moteur de sécurité interrogeant l'API publique Google OSV.dev (api.osv.dev/v1/query).
    Effectue l'analyse différentielle entre la version actuellement installée et la version candidate.
    """

    def __init__(self, timeout: float = 15.0):
        self.timeout = timeout
        self.osv_url = "https://api.osv.dev/v1/query"

    @staticmethod
    def map_ecosystem(registry_name_or_ecosystem: str) -> str:
        eco = (registry_name_or_ecosystem or "").strip().lower()
        if eco in ["pypi", "python", "pip"]:
            return "PyPI"
        elif eco in ["npm", "node", "javascript", "typescript"]:
            return "npm"
        elif eco in ["maven", "maven central", "java"]:
            return "Maven"
        elif eco in ["docker", "dockerhub", "docker hub", "container"]:
            return "Linux"
        return "PyPI"

    async def query_vulnerabilities(self, package_name: str, version: str, ecosystem: str) -> List[Dict[str, Any]]:
        if not version or version == "unknown":
            return []

        payload = {
            "package": {
                "name": package_name,
                "ecosystem": self.map_ecosystem(ecosystem)
            },
            "version": version
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.post(self.osv_url, json=payload)
                if response.status_code == 200:
                    data = response.json()
                    vulns = data.get("vulns", [])
                    result = []
                    for v in vulns:
                        summary = v.get("summary") or v.get("details") or "No summary available"
                        severity = "MEDIUM"
                        if v.get("database_specific"):
                            severity = v.get("database_specific").get("severity", severity)
                        result.append({
                            "id": v.get("id"),
                            "summary": summary[:200],
                            "details": v.get("details", ""),
                            "severity": severity,
                            "aliases": v.get("aliases", []),
                            "published": v.get("published")
                        })
                    return result
                return []
            except Exception:
                return []

    async def analyze_differential(self, package_name: str, current_version: str, candidate_version: str, ecosystem: str) -> Dict[str, Any]:
        current_vulns = await self.query_vulnerabilities(package_name, current_version, ecosystem)

        if not candidate_version or candidate_version == current_version:
            candidate_vulns = current_vulns
        else:
            candidate_vulns = await self.query_vulnerabilities(package_name, candidate_version, ecosystem)

        current_ids = {v["id"] for v in current_vulns}
        candidate_ids = {v["id"] for v in candidate_vulns}

        fixed_ids = current_ids - candidate_ids
        remaining_ids = current_ids & candidate_ids
        new_ids = candidate_ids - current_ids

        fixed_vulns = [v for v in current_vulns if v["id"] in fixed_ids]
        remaining_vulns = [v for v in candidate_vulns if v["id"] in remaining_ids]
        new_vulns = [v for v in candidate_vulns if v["id"] in new_ids]

        return {
            "package_name": package_name,
            "current_version": current_version,
            "candidate_version": candidate_version,
            "current_vulnerabilities_count": len(current_vulns),
            "candidate_vulnerabilities_count": len(candidate_vulns),
            "resolved_cves_count": len(fixed_vulns),
            "current_vulnerabilities": current_vulns,
            "candidate_vulnerabilities": candidate_vulns,
            "resolved_vulnerabilities": fixed_vulns,
            "remaining_vulnerabilities": remaining_vulns,
            "new_vulnerabilities": new_vulns,
        }

    @classmethod
    async def evaluate_dependency(cls, package_name: str, current_version: str, ecosystem: str = "pypi") -> SimpleOSVReport:
        checker = cls()
        adapter = RegistryAdapterFactory.get_adapter(ecosystem)
        reg_res = await adapter.get_latest_version(package_name)
        latest_version = reg_res.get("latest_version") or current_version

        diff = await checker.analyze_differential(package_name, current_version, latest_version, ecosystem)
        is_outdated = (latest_version != current_version)
        resolved_count = diff["resolved_cves_count"]

        if resolved_count > 0:
            rec_status = "FAVORABLE"
            explanation = f"Mise à jour fortement recommandée : passage de {current_version} à {latest_version} résout {resolved_count} vulnérabilité(s)."
        elif is_outdated:
            rec_status = "FAVORABLE"
            explanation = f"Mise à jour vers {latest_version} disponible."
        else:
            rec_status = "UP_TO_DATE"
            explanation = f"La dépendance {package_name} est déjà à jour (version {current_version})."

        return SimpleOSVReport(
            package_name=package_name,
            current_version=current_version,
            latest_version=latest_version,
            is_outdated=is_outdated,
            current_cve_count=diff["current_vulnerabilities_count"],
            latest_cve_count=diff["candidate_vulnerabilities_count"],
            recommendation_status=rec_status,
            explanation_markdown=explanation
        )

# Alias pour compatibilité
OSVSecurityChecker = OSVChecker
