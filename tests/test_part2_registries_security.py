import pytest
import asyncio
from common.registry_adapters.factory import RegistryAdapterFactory
from common.security.osv_checker import OSVSecurityChecker

@pytest.mark.anyio
async def test_pypi_registry_adapter():
    adapter = RegistryAdapterFactory.get_adapter("pypi")
    assert adapter is not None
    latest = await adapter.get_latest_version("requests")
    assert latest is not None
    print(f"\n[PyPI Test] Package 'requests' -> Latest version: {latest}")

@pytest.mark.anyio
async def test_npm_registry_adapter():
    adapter = RegistryAdapterFactory.get_adapter("npm")
    assert adapter is not None
    latest = await adapter.get_latest_version("express")
    assert latest is not None
    print(f"\n[npm Test] Package 'express' -> Latest version: {latest}")

@pytest.mark.anyio
async def test_osv_security_checker():
    report = await OSVSecurityChecker.evaluate_dependency(
        package_name="requests",
        current_version="2.25.1",
        ecosystem="pypi"
    )
    assert report.package_name == "requests"
    assert report.is_outdated is True
    assert report.current_cve_count > 0
    print(f"\n[OSV Security Report Test]")
    print(f"  Package: {report.package_name} (Current: {report.current_version} -> Latest: {report.latest_version})")
    print(f"  Status: {report.recommendation_status}")
    print(f"  Current CVEs: {report.current_cve_count} | Candidate CVEs: {report.latest_cve_count}")
    print(f"  Explanation: {report.explanation_markdown}")

if __name__ == "__main__":
    asyncio.run(test_pypi_registry_adapter())
    asyncio.run(test_npm_registry_adapter())
    asyncio.run(test_osv_security_checker())
