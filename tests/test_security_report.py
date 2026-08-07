from common.schemas.DependencySecurityReport import (
    DependencySecurityReport,
    DependencySecurityDelta,
    VulnerabilityItem
)

def test_security_report_markdown_generation():
    delta = DependencySecurityDelta(
        package_name="django",
        registry="PyPI",
        current_version="2.2",
        latest_version="4.2.10",
        current_vulnerabilities_count=5,
        candidate_vulnerabilities_count=0,
        resolved_cves_count=5,
        resolved_vulnerabilities=[
            VulnerabilityItem(id="CVE-2021-3281", summary="SQL Injection vulnerability in Django 2.2", severity="HIGH")
        ],
        recommendation="FAVORABLE",
        rationale="Mise à jour fortement recommandée de 2.2 vers 4.2.10."
    )

    report = DependencySecurityReport(
        repository_name="my-org/my-project",
        total_dependencies=1,
        up_to_date_count=0,
        updates_available_count=1,
        resolved_cves_total=5,
        overall_recommendation="FAVORABLE",
        executive_summary="Le projet présente un profil de mise à jour très favorable.",
        dependency_deltas=[delta]
    )

    md = report.to_markdown()
    assert "# 🛡️ Rapport de Sécurité des Dépendances — my-org/my-project" in md
    assert "django" in md
    assert "CVE-2021-3281" in md
    assert "FAVORABLE" in md
