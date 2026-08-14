import asyncio
import pytest

from common.schemas.Registry import Registry
from common.schemas.DependencySecurityReport import DependencySecurityReport
from common.schemas.ManifestFileSecurityReport import ManifestFileSecurityReport
from common.schemas.ManifestFileUpdateContext import ManifestFileUpdateContext
from security_intelligence_service.service import process_security_intelligence

def test_process_security_intelligence_structure():
    npm_registry = Registry(name="npm", url="https://registry.npmjs.org/")
    dummy_report_current = DependencySecurityReport(
        name="bootstrap",
        version="5.2.0",
        registry=npm_registry,
        vulnerabilities=[]
    )
    dummy_report_candidate = DependencySecurityReport(
        name="bootstrap",
        version="5.3.3",
        registry=npm_registry,
        vulnerabilities=[]
    )
    
    current_manifest_report = ManifestFileSecurityReport(
        path="package.json",
        dependencies_security_reports=[dummy_report_current],
        dev_dependencies_security_reports=[]
    )
    candidate_manifest_report = ManifestFileSecurityReport(
        path="package.json",
        dependencies_security_reports=[dummy_report_candidate],
        dev_dependencies_security_reports=[]
    )

    context = ManifestFileUpdateContext(
        current_manifest_file_report=current_manifest_report,
        candidate_manifest_file_report=candidate_manifest_report
    )

    result = asyncio.run(process_security_intelligence("test-repo", [context]))
    assert result["repository_name"] == "test-repo"
    assert result["processed_count"] == 1
    assert len(result["details"]) == 1
    assert result["details"][0]["recommendation"] in ["FAVORABLE", "CAUTIOUS", "DISCOURAGED"]
