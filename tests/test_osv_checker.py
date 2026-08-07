import pytest
from common.security.osv_checker import OSVChecker

def test_map_ecosystem():
    assert OSVChecker.map_ecosystem("PyPI") == "PyPI"
    assert OSVChecker.map_ecosystem("npm") == "npm"
    assert OSVChecker.map_ecosystem("Maven Central") == "Maven"
    assert OSVChecker.map_ecosystem("Docker Hub") == "Linux"

@pytest.mark.anyio
async def test_osv_differential_analysis():
    checker = OSVChecker()
    # Test with a known package version with vulnerabilities (django 2.2) vs candidate (django 4.2.10)
    diff = await checker.analyze_differential("django", "2.2", "4.2.10", "PyPI")
    assert diff["package_name"] == "django"
    assert diff["current_version"] == "2.2"
    assert diff["candidate_version"] == "4.2.10"
    assert diff["current_vulnerabilities_count"] > 0
    assert diff["resolved_cves_count"] > 0
