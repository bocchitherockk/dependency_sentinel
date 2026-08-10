import asyncio

from common.schemas.Dependency import Dependency
from common.schemas.ManifestFile import ManifestFile
from common.schemas.DependencySecurityReport import DependencySecurityReport
from common.schemas.ManifestFileSecurityReport import ManifestFileSecurityReport
from common.schemas.DependencyUpdateContext import DependencyUpdateContext
from common.schemas.ManifestFileUpdateContext import ManifestFileUpdateContext
from registry_service.registry_adapters.base_registry_adapter import BaseRegistryAdapter
from registry_service.registry_selector import RegistrySelector
from registry_service.security_registry import SecurityRegistry

async def get_candidate_dependency(dependency: Dependency) -> Dependency:
    registry_adapter: BaseRegistryAdapter = RegistrySelector.get_adapter(dependency.registry.name)
    candidate_dependency: Dependency = await registry_adapter.get_latest_version(dependency)
    return candidate_dependency

async def get_candidate_manifest_file(manifest_file: ManifestFile) -> ManifestFile:
    dependencies, dev_dependencies = await asyncio.gather(
        asyncio.gather(*[get_candidate_dependency(dependency) for dependency in manifest_file.dependencies]),
        asyncio.gather(*[get_candidate_dependency(dev_dependency) for dev_dependency in manifest_file.dev_dependencies])
    )
    return ManifestFile(
        path=manifest_file.path,
        dependencies=dependencies,
        dev_dependencies=dev_dependencies,
    )

async def get_dependency_security_report(dependency: Dependency) -> DependencySecurityReport:
    vulnerabilities = await SecurityRegistry.query_vulnerabilities(dependency)
    return DependencySecurityReport(
        name=dependency.name,
        version=dependency.version,
        registry=dependency.registry,
        vulnerabilities=vulnerabilities,
    )

async def get_manifest_file_security_report(manifest_file: ManifestFile) -> ManifestFileSecurityReport:
    dependencies_security_reports, dev_dependencies_security_reports = await asyncio.gather(
        asyncio.gather(*[get_dependency_security_report(dependency) for dependency in manifest_file.dependencies]),
        asyncio.gather(*[get_dependency_security_report(dev_dependency) for dev_dependency in manifest_file.dev_dependencies])
    )
    return ManifestFileSecurityReport(
        path=manifest_file.path,
        dependencies=manifest_file.dependencies,
        dev_dependencies=manifest_file.dev_dependencies,
        dependencies_security_reports=dependencies_security_reports,
        dev_dependencies_security_reports=dev_dependencies_security_reports,
    )

async def get_dependency_update_context(dependency: Dependency) -> DependencyUpdateContext:
    candidate_dependency: Dependency = await get_candidate_dependency(dependency)
    current_security_report, candidate_security_report = await asyncio.gather(
        get_dependency_security_report(dependency),
        get_dependency_security_report(candidate_dependency)
    )
    return DependencyUpdateContext(
        current_dependency_report=current_security_report,
        candidate_dependency_report=candidate_security_report,
    )

async def get_manifest_file_update_context(manifest_file: ManifestFile) -> ManifestFileUpdateContext:
    candidate_manifest_file: ManifestFile = await get_candidate_manifest_file(manifest_file)
    current_manifest_file_security_report, candidate_manifest_file_security_report = await asyncio.gather(
        get_manifest_file_security_report(manifest_file),
        get_manifest_file_security_report(candidate_manifest_file)
    )
    return ManifestFileUpdateContext(
        current_manifest_file_report=current_manifest_file_security_report,
        candidate_manifest_file_report=candidate_manifest_file_security_report
    )
