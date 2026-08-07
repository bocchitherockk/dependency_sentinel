from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime, timezone

class VulnerabilityItem(BaseModel):
    id: str
    summary: str
    severity: str = "MEDIUM"
    details: Optional[str] = None
    aliases: List[str] = Field(default_factory=list)

class DependencySecurityDelta(BaseModel):
    package_name: str
    registry: str
    current_version: str
    latest_version: str
    current_vulnerabilities_count: int = 0
    candidate_vulnerabilities_count: int = 0
    resolved_cves_count: int = 0
    resolved_vulnerabilities: List[VulnerabilityItem] = Field(default_factory=list)
    remaining_vulnerabilities: List[VulnerabilityItem] = Field(default_factory=list)
    new_vulnerabilities: List[VulnerabilityItem] = Field(default_factory=list)
    license: Optional[str] = None
    recommendation: str = "FAVORABLE"  # FAVORABLE, CAUTIOUS, DISCOURAGED
    rationale: str = ""

class DependencySecurityReport(BaseModel):
    repository_name: str
    scanned_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    total_dependencies: int = 0
    up_to_date_count: int = 0
    updates_available_count: int = 0
    resolved_cves_total: int = 0
    overall_recommendation: str = "FAVORABLE"  # FAVORABLE, CAUTIOUS, DISCOURAGED
    executive_summary: str = ""
    dependency_deltas: List[DependencySecurityDelta] = Field(default_factory=list)

    def to_markdown(self) -> str:
        """
        Génère un rapport explicatif clair au format Markdown destiné au développeur.
        """
        md = []
        md.append(f"# 🛡️ Rapport de Sécurité des Dépendances — {self.repository_name}")
        md.append(f"*Date de l'analyse : {self.scanned_at.strftime('%Y-%m-%d %H:%M:%S UTC')}*\n")

        md.append("## 📊 Synthèse Globale")
        md.append(f"- **Total des dépendances analysées** : {self.total_dependencies}")
        md.append(f"- **Dépendances à jour** : {self.up_to_date_count}")
        md.append(f"- **Mises à jour disponibles** : {self.updates_available_count}")
        md.append(f"- **Failles de sécurité (CVEs) corrigibles** : {self.resolved_cves_total}")
        md.append(f"- **Verdict Global** : **{self.overall_recommendation}**\n")

        md.append("### 📝 Résumé Exécutif")
        md.append(f"{self.executive_summary}\n")

        md.append("---")
        md.append("## 🔍 Analyse Détaillée par Dépendance\n")

        for delta in self.dependency_deltas:
            status_icon = "✅" if delta.recommendation == "FAVORABLE" else ("⚠️" if delta.recommendation == "CAUTIOUS" else "❌")
            md.append(f"### {status_icon} `{delta.package_name}` ({delta.registry})")
            md.append(f"- **Version installée** : `{delta.current_version}`")
            md.append(f"- **Dernière version candidate** : `{delta.latest_version}`")
            md.append(f"- **CVEs résolues par la MàJ** : `{delta.resolved_cves_count}`")
            md.append(f"- **Recommandation** : **{delta.recommendation}**")
            md.append(f"- **Explication** : {delta.rationale}\n")

            if delta.resolved_vulnerabilities:
                md.append("  #### 🔓 Failles de sécurité corrigées :")
                for vuln in delta.resolved_vulnerabilities:
                    md.append(f"  - **{vuln.id}** ({vuln.severity}) : {vuln.summary}")
                md.append("")

            if delta.remaining_vulnerabilities:
                md.append("  #### ⚠️ Failles encore présentes dans la version candidate :")
                for vuln in delta.remaining_vulnerabilities:
                    md.append(f"  - **{vuln.id}** ({vuln.severity}) : {vuln.summary}")
                md.append("")

        return "\n".join(md)
