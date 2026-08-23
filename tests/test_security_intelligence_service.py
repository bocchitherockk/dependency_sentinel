import sys
import os
from pathlib import Path

root_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root_dir / "libs" / "common" / "src"))
sys.path.insert(0, str(root_dir / "libs" / "events" / "src"))
sys.path.insert(0, str(root_dir / "services" / "security_intelligence_service" / "src"))

import pytest
import asyncio
from common.schemas.DependencySecurityReport import DependencySecurityReport
from common.schemas.DependencyUpdateContext import DependencyUpdateContext
from common.schemas.ManifestFileUpdateContext import ManifestFileUpdateContext
from security_intelligence_service.service import analyze_update_context_and_update_manifests

@pytest.mark.anyio
async def test_analyze_update_context_structure():
    current_report = DependencySecurityReport(
        name="requests",
        version="2.25.1",
        registry_name="pypi",
        vulnerabilities=[]
    )
    latest_report = DependencySecurityReport(
        name="requests",
        version="2.34.2",
        registry_name="pypi",
        vulnerabilities=[]
    )
    
    dep_context = DependencyUpdateContext(
        current_version_dependency_report=current_report,
        latest_compatible_version_dependency_report=current_report,
        latest_version_dependency_report=latest_report
    )
    
    manifest_context = ManifestFileUpdateContext(
        manifest_file_path="requirements.txt",
        dependencies_update_context=[dep_context],
        dev_dependencies_update_context=[]
    )

    branch_name, summary = await analyze_update_context_and_update_manifests("test-repo", [manifest_context])
    print(f"Test Result -> Branch: {branch_name}, Summary: {summary[:100] if summary else 'None'}")

if __name__ == "__main__":
    asyncio.run(test_analyze_update_context_structure())
