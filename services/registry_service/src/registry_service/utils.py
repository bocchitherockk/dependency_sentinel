import asyncio
from logging import Logger

from common.logging.global_logger import get_global_logger
from common.schemas.Dependency import Dependency
from common.schemas.ManifestFile import ManifestFile
from common.schemas.DependencySecurityReport import DependencySecurityReport
from common.schemas.DependencyUpdateContext import DependencyUpdateContext
from common.schemas.ManifestFileUpdateContext import ManifestFileUpdateContext

from registry_service.registry_adapters.base_registry_adapter import BaseRegistryAdapter
from registry_service.registry_selector import RegistrySelector
from registry_service.security_registry import SecurityRegistry

logger: Logger = get_global_logger(__name__)

async def get_candidate_dependencies(dependency: Dependency) -> tuple[Dependency, Dependency] | None:
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

async def get_dependency_update_context(dependency: Dependency) -> DependencyUpdateContext | None:
    result = await get_candidate_dependencies(dependency)
    if result is None:
        return None

    latest_compatible_version_dependency, latest_version_dependency = result
    current_version_dependency_report, latest_compatible_version_dependency_report, latest_version_dependency_report = await asyncio.gather(
        get_dependency_security_report(dependency),
        get_dependency_security_report(latest_compatible_version_dependency),
        get_dependency_security_report(latest_version_dependency)
    )
    result: DependencyUpdateContext = DependencyUpdateContext(
        current_version_dependency_report=current_version_dependency_report,
        latest_compatible_version_dependency_report=latest_compatible_version_dependency_report,
        latest_version_dependency_report=latest_version_dependency_report,
    )
    logger.info(f"DependencyUpdateContext generated for dependency '{dependency.name}' with current version '{dependency.version}' in registry '{dependency.registry_name}'.")
    logger.debug(f'DependencyUpdateContext details: {result}')
    return result

async def get_manifest_file_update_context(manifest_file: ManifestFile) -> ManifestFileUpdateContext:
    dependencies_update_context, dev_dependencies_update_context = await asyncio.gather(
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

    # we filter out None values from the dependencies_update_context and dev_dependencies_update_context lists
    dependencies_update_context = [context for context in dependencies_update_context if context is not None]
    dev_dependencies_update_context = [context for context in dev_dependencies_update_context if context is not None]

    result: ManifestFileUpdateContext = ManifestFileUpdateContext(
        manifest_file_path=manifest_file.path,
        dependencies_update_context=dependencies_update_context,
        dev_dependencies_update_context=dev_dependencies_update_context,
    )
    logger.info(f"ManifestFileUpdateContext generated for manifest file '{manifest_file.path}'.")
    logger.debug(f'ManifestFileUpdateContext details: {result}')
    return result
