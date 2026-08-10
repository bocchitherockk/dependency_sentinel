import asyncio

from common.schemas.Dependency import Dependency
from common.schemas.DependencySecurityReport import DependencySecurityReport
from common.schemas.DependencyUpdateContext import DependencyUpdateContext
from common.schemas.ManifestFile import ManifestFile
from common.schemas.ManifestFileSecurityReport import ManifestFileSecurityReport
from common.schemas.ManifestFileUpdateContext import ManifestFileUpdateContext
from common.schemas.Registry import Registry
from common.schemas.VulnerabilityItem import VulnerabilityItem
from registry_service import utils


def _dependency(name: str, version: str, registry_name: str = "pypi") -> Dependency:
    return Dependency(name=name, version=version, registry=Registry(name=registry_name, url="https://example.invalid"))


def test_get_candidate_dependency_uses_selected_registry(monkeypatch):
    dependency = _dependency("requests", "2.31.0")
    candidate = _dependency("requests", "2.32.0")

    class FakeAdapter:
        @staticmethod
        async def get_latest_version(value: Dependency) -> Dependency:
            assert value == dependency
            return candidate

    monkeypatch.setattr(utils.RegistrySelector, "get_adapter", staticmethod(lambda registry_name: FakeAdapter))

    result = asyncio.run(utils.get_candidate_dependency(dependency))

    assert result == candidate


def test_get_candidate_manifest_file_updates_all_dependencies(monkeypatch):
    manifest = ManifestFile(
        path="requirements.txt",
        dependencies=[_dependency("requests", "2.31.0")],
        dev_dependencies=[_dependency("pytest", "8.0.0")],
    )

    async def fake_get_candidate_dependency(dependency: Dependency) -> Dependency:
        return _dependency(dependency.name, f"{dependency.version}.candidate", dependency.registry.name)

    monkeypatch.setattr(utils, "get_candidate_dependency", fake_get_candidate_dependency)

    result = asyncio.run(utils.get_candidate_manifest_file(manifest))

    assert [item.version for item in result.dependencies] == ["2.31.0.candidate"]
    assert [item.version for item in result.dev_dependencies] == ["8.0.0.candidate"]


def test_get_dependency_security_report_wraps_vulnerabilities(monkeypatch):
    dependency = _dependency("requests", "2.31.0")
    vulnerabilities = [VulnerabilityItem(id="CVE-1", summary="s", details="d", severity="HIGH", aliases=[])]

    async def fake_query_vulnerabilities(value: Dependency):
        return vulnerabilities

    monkeypatch.setattr(utils.SecurityRegistry, "query_vulnerabilities", staticmethod(fake_query_vulnerabilities))

    result = asyncio.run(utils.get_dependency_security_report(dependency))

    assert isinstance(result, DependencySecurityReport)
    assert result.name == dependency.name
    assert result.vulnerabilities == vulnerabilities


def test_get_manifest_file_security_report_wraps_dependency_reports(monkeypatch):
    manifest = ManifestFile(
        path="requirements.txt",
        dependencies=[_dependency("requests", "2.31.0")],
        dev_dependencies=[_dependency("pytest", "8.0.0")],
    )

    async def fake_get_dependency_security_report(dependency: Dependency) -> DependencySecurityReport:
        return DependencySecurityReport(
            name=dependency.name,
            version=dependency.version,
            registry=dependency.registry,
            vulnerabilities=[],
        )

    monkeypatch.setattr(utils, "get_dependency_security_report", fake_get_dependency_security_report)

    result = asyncio.run(utils.get_manifest_file_security_report(manifest))

    assert isinstance(result, ManifestFileSecurityReport)
    assert [item.name for item in result.dependencies_security_reports] == ["requests"]
    assert [item.name for item in result.dev_dependencies_security_reports] == ["pytest"]


def test_get_dependency_update_context_uses_current_and_candidate_reports(monkeypatch):
    dependency = _dependency("requests", "2.31.0")
    candidate = _dependency("requests", "2.32.0")

    current_report = DependencySecurityReport(name=dependency.name, version=dependency.version, registry=dependency.registry, vulnerabilities=[])
    candidate_report = DependencySecurityReport(name=candidate.name, version=candidate.version, registry=candidate.registry, vulnerabilities=[])

    async def fake_get_candidate_dependency(value: Dependency) -> Dependency:
        return candidate

    async def fake_get_dependency_security_report(value: Dependency) -> DependencySecurityReport:
        return current_report if value == dependency else candidate_report

    monkeypatch.setattr(utils, "get_candidate_dependency", fake_get_candidate_dependency)
    monkeypatch.setattr(utils, "get_dependency_security_report", fake_get_dependency_security_report)

    result = asyncio.run(utils.get_dependency_update_context(dependency))

    assert isinstance(result, DependencyUpdateContext)
    assert result.current_dependency_report == current_report
    assert result.candidate_dependency_report == candidate_report


def test_get_manifest_file_update_context_uses_current_and_candidate_reports(monkeypatch):
    manifest = ManifestFile(
        path="requirements.txt",
        dependencies=[_dependency("requests", "2.31.0")],
        dev_dependencies=[],
    )
    candidate_manifest = ManifestFile(
        path="requirements.txt",
        dependencies=[_dependency("requests", "2.32.0")],
        dev_dependencies=[],
    )

    current_report = ManifestFileSecurityReport(path=manifest.path, dependencies=manifest.dependencies, dev_dependencies=manifest.dev_dependencies)
    candidate_report = ManifestFileSecurityReport(path=candidate_manifest.path, dependencies=candidate_manifest.dependencies, dev_dependencies=candidate_manifest.dev_dependencies)

    async def fake_get_candidate_manifest_file(value: ManifestFile) -> ManifestFile:
        return candidate_manifest

    async def fake_get_manifest_file_security_report(value: ManifestFile) -> ManifestFileSecurityReport:
        return current_report if value == manifest else candidate_report

    monkeypatch.setattr(utils, "get_candidate_manifest_file", fake_get_candidate_manifest_file)
    monkeypatch.setattr(utils, "get_manifest_file_security_report", fake_get_manifest_file_security_report)

    result = asyncio.run(utils.get_manifest_file_update_context(manifest))

    assert isinstance(result, ManifestFileUpdateContext)
    assert result.current_manifest_file_report == current_report
    assert result.candidate_manifest_file_report == candidate_report
