import asyncio

from common.schemas.Dependency import Dependency
from common.schemas.ManifestFile import ManifestFile
from common.schemas.DependencySecurityReport import DependencySecurityReport
from common.schemas.DependencyUpdateContext import DependencyUpdateContext
from common.schemas.ManifestFileUpdateContext import ManifestFileUpdateContext
from registry_service.registry_adapters.base_registry_adapter import BaseRegistryAdapter
from registry_service.registry_selector import RegistrySelector
from registry_service.security_registry import SecurityRegistry

# Semaphore to prevent rate limiting from libraries.io
_registry_semaphore = asyncio.Semaphore(3)

async def get_candidate_dependencies(dependency: Dependency) -> tuple[Dependency, Dependency]:
    async with _registry_semaphore:
        registry_adapter: BaseRegistryAdapter = RegistrySelector.get_adapter(dependency.registry_name)
        candidate_versions_dependencies: tuple[Dependency, Dependency] = await registry_adapter.get_candidate_versions_dependencies(dependency)
        await asyncio.sleep(0.5) # Slight delay to respect rate limits
        return candidate_versions_dependencies

async def get_dependency_security_report(dependency: Dependency) -> DependencySecurityReport:
    vulnerabilities = await SecurityRegistry.query_vulnerabilities(dependency)
    return DependencySecurityReport(
        name=dependency.name,
        version=dependency.version,
        registry_name=dependency.registry_name,
        vulnerabilities=vulnerabilities,
    )

async def get_dependency_update_context(dependency: Dependency) -> DependencyUpdateContext | None:
    try:
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
    except Exception as e:
        import logging
        logging.error(f"Failed to get update context for dependency {dependency.name}: {e}")
        return None

async def get_manifest_file_update_context(manifest_file: ManifestFile) -> ManifestFileUpdateContext:
    dependencies_results, dev_dependencies_results = await asyncio.gather(
        asyncio.gather(*[
            get_dependency_update_context(dependency)
            for dependency in manifest_file.dependencies
            if dependency.registry_name is not None
        ]),
        asyncio.gather(*[
            get_dependency_update_context(dependency)
            for dependency in manifest_file.dev_dependencies
            if dependency.registry_name is not None
        ])
    )
    
    dependencies_update_context = [ctx for ctx in dependencies_results if ctx is not None]
    dev_dependencies_update_context = [ctx for ctx in dev_dependencies_results if ctx is not None]

    return ManifestFileUpdateContext(
        manifest_file_path=manifest_file.path,
        dependencies_update_context=dependencies_update_context,
        dev_dependencies_update_context=dev_dependencies_update_context,
    )
