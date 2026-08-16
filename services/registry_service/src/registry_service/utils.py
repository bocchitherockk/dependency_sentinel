import asyncio

from common.schemas.Dependency import Dependency
from common.schemas.ManifestFile import ManifestFile
from common.schemas.DependencySecurityReport import DependencySecurityReport
from common.schemas.DependencyUpdateContext import DependencyUpdateContext
from common.schemas.ManifestFileUpdateContext import ManifestFileUpdateContext
from registry_service.registry_adapters.base_registry_adapter import BaseRegistryAdapter
from registry_service.registry_selector import RegistrySelector
from registry_service.security_registry import SecurityRegistry

async def get_candidate_dependencies(dependency: Dependency) -> tuple[Dependency, Dependency]:
    registry_adapter: BaseRegistryAdapter = RegistrySelector.get_adapter(dependency.registry_name)
    candidate_versions_dependencies: tuple[Dependency, Dependency] = await registry_adapter.get_candidate_versions_dependencies(dependency)
    return candidate_versions_dependencies

async def get_dependency_security_report(dependency: Dependency) -> DependencySecurityReport:
    vulnerabilities = await SecurityRegistry.query_vulnerabilities(dependency)
    return DependencySecurityReport(
        name=dependency.name,
        version=dependency.version,
        registry_name=dependency.registry_name,
        vulnerabilities=vulnerabilities,
    )

async def get_dependency_update_context(dependency: Dependency) -> DependencyUpdateContext:
    latest_compatible_version_dependency, latest_version_dependency = await get_candidate_dependencies(dependency)
    current_version_dependency_report, latest_compatible_version_dependency_report, latest_version_dependency_report = await asyncio.gather(
        get_dependency_security_report(dependency),
        get_dependency_security_report(latest_compatible_version_dependency),
        get_dependency_security_report(latest_version_dependency)
    )
    return DependencyUpdateContext(
        current_version_dependency_report=current_version_dependency_report,
        latest_compatible_version_dependency_report=latest_compatible_version_dependency_report,
        latest_version_dependency_report=latest_version_dependency_report,
    )

async def get_manifest_file_update_context(manifest_file: ManifestFile) -> ManifestFileUpdateContext:
    dependencies_update_context, dev_dependencies_update_context = await asyncio.gather(
        asyncio.gather(*[
            get_dependency_update_context(dependency) for dependency in manifest_file.dependencies
        ]),
        asyncio.gather(*[
            get_dependency_update_context(dependency) for dependency in manifest_file.dev_dependencies
        ])
    )
    return ManifestFileUpdateContext(
        manifest_file_path=manifest_file.path,
        dependencies_update_context=dependencies_update_context,
        dev_dependencies_update_context=dev_dependencies_update_context,
    )
