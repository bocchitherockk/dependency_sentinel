import os
from typing import override
from logging import Logger

import httpx
import semver
from dotenv import load_dotenv

from common.logging.global_logger import get_global_logger
from common.schemas.Dependency import Dependency
from registry_service.registry_adapters.base_registry_adapter import BaseRegistryAdapter

logger: Logger = get_global_logger(__name__)

load_dotenv()
logger.info('Environment variables loaded from .env file.')
logger.debug('Environment variables: ')
logger.debug(f'    LIBRARIES_IO_API_KEY: {os.getenv("LIBRARIES_IO_API_KEY")}')


class LibrariesIORegistryAdapter(BaseRegistryAdapter):
    _supported_registries: list[str] | None = None
    base_url: str = 'https://libraries.io/api'
    api_key:  str = os.getenv('LIBRARIES_IO_API_KEY', None)

    @override
    @staticmethod
    def get_supported_registries() -> list[str]:
        if LibrariesIORegistryAdapter._supported_registries is None:
            url: str = f'{LibrariesIORegistryAdapter.base_url}/platforms'
            params = {'api_key': LibrariesIORegistryAdapter.api_key} if LibrariesIORegistryAdapter.api_key is not None else {}
            response = httpx.get(url, params=params, timeout=None)
            response.raise_for_status()
            data = response.json()
            logger.info(f'Fetched supported registries for Libraries.io')
            logger.debug(f'Supported registries details: {data}')
            LibrariesIORegistryAdapter._supported_registries = [platform['name'] for platform in data]

        return LibrariesIORegistryAdapter._supported_registries

    @override
    @staticmethod
    def correct_registry_name(registry_name: str) -> str:
        for supported_registry in LibrariesIORegistryAdapter.get_supported_registries():
            if supported_registry.lower() == registry_name.lower():
                logger.info(f"Registry '{registry_name}' is supported by Libraries.io as '{supported_registry}'.")
                return supported_registry

        logger.error(f"Registry '{registry_name}' is not supported by Libraries.io. Supported registries: {LibrariesIORegistryAdapter.supported_registries}")
        raise ValueError(f"Registry '{registry_name}' is not supported by Libraries.io. Supported registries: {LibrariesIORegistryAdapter.supported_registries}")

    @override
    @staticmethod
    async def get_all_versions_dependencies(dependency: Dependency) -> list[Dependency]:
        safe_dependency_name: str = dependency.name.replace('/', '%2F')
        corrected_registry_name: str = LibrariesIORegistryAdapter.correct_registry_name(dependency.registry_name)
        url: str = f'{LibrariesIORegistryAdapter.base_url}/{corrected_registry_name}/{safe_dependency_name}'
        params = {'api_key': LibrariesIORegistryAdapter.api_key} if LibrariesIORegistryAdapter.api_key is not None else {}

        async with httpx.AsyncClient(timeout=None) as client:
            response = await client.get(url, params=params)

        response.raise_for_status()
        data = response.json()
        result: list[Dependency] = [
            Dependency(
                name=dependency.name,
                version=version['number'],
                registry=dependency.registry,
            )
            for version in data['versions']
        ]
        logger.info(f"Found {len(result)} versions for dependency '{dependency.name}' in registry '{corrected_registry_name}'.")
        logger.debug(f"Versions details: {result}")
        return result

    @override
    @staticmethod
    async def get_latest_version_dependency(dependency: Dependency) -> Dependency:
        safe_dependency_name: str = dependency.name.replace('/', '%2F')
        corrected_registry_name: str = LibrariesIORegistryAdapter.correct_registry_name(dependency.registry_name)
        url: str = f'{LibrariesIORegistryAdapter.base_url}/{corrected_registry_name}/{safe_dependency_name}'
        params = {'api_key': LibrariesIORegistryAdapter.api_key} if LibrariesIORegistryAdapter.api_key is not None else {}

        async with httpx.AsyncClient(timeout=None) as client:
            response = await client.get(url, params=params)

        response.raise_for_status()
        data = response.json()
        latest_stable_release_number: str = data['latest_stable_release_number']

        latest_version_dependency: Dependency = Dependency(
            name=dependency.name,
            version=latest_stable_release_number,
            registry=dependency.registry,
        )
        logger.info(f"Latest version for dependency '{dependency.name}' fetched in registry '{corrected_registry_name}' is '{latest_stable_release_number}'.")
        return latest_version_dependency

    @override
    @staticmethod
    async def get_latest_compatible_version_dependency(dependency: Dependency) -> Dependency:
        safe_dependency_name: str = dependency.name.replace('/', '%2F')
        corrected_registry_name: str = LibrariesIORegistryAdapter.correct_registry_name(dependency.registry_name)
        url: str = f'{LibrariesIORegistryAdapter.base_url}/{corrected_registry_name}/{safe_dependency_name}'
        params = { 'api_key': LibrariesIORegistryAdapter.api_key } if LibrariesIORegistryAdapter.api_key is not None else {}

        async with httpx.AsyncClient(timeout=None) as client:
            response = await client.get(url, params=params)

        response.raise_for_status()
        data = response.json()

        # TODO: this is a quick workaround to get the exact version
        current_version = semver.VersionInfo.parse(dependency.version.lstrip("^~<>="))
        # Search for the latest compatible version in the versions list
        # We iterate in reverse because the result is likely to be towards the end of the list
        for i in range(len(data['versions']) - 1, -1, -1):
            iter_version = semver.VersionInfo.parse(data['versions'][i]['number'])
            if iter_version.major == current_version.major:
                latest_compatible_version_dependency: Dependency = Dependency(
                    name=dependency.name,
                    version=data['versions'][i]['number'],
                    registry_name=dependency.registry_name,
                )
                logger.info(f"Latest compatible version for dependency '{dependency.name}' with version '{dependency.version}' in registry '{corrected_registry_name}' is '{latest_compatible_version_dependency.version}'.")
                return latest_compatible_version_dependency
            logger.debug(f"Version '{data['versions'][i]['number']}' is not compatible with current version '{dependency.version}' for dependency '{dependency.name}' in registry '{corrected_registry_name}'.")

        logger.error(f"No compatible version found for dependency '{dependency.name}' with version '{dependency.version}' in registry '{corrected_registry_name}'.")
        raise ValueError(f"No compatible version found for dependency '{dependency.name}' with version '{dependency.version}' in registry '{dependency.registry_name}'.")

    @override
    @staticmethod
    async def get_candidate_versions_dependencies(dependency: Dependency) -> tuple[Dependency, Dependency]:
        safe_dependency_name: str = dependency.name.replace('/', '%2F')
        corrected_registry_name: str = LibrariesIORegistryAdapter.correct_registry_name(dependency.registry_name)
        url: str = f'{LibrariesIORegistryAdapter.base_url}/{corrected_registry_name}/{safe_dependency_name}'
        params = {'api_key': LibrariesIORegistryAdapter.api_key} if LibrariesIORegistryAdapter.api_key is not None else {}

        async with httpx.AsyncClient(timeout=None) as client:
            response = await client.get(url, params=params)

        response.raise_for_status()
        data = response.json()
        latest_stable_release_number: str = data['latest_stable_release_number']

        latest_version_dependency: Dependency = Dependency(
            name=dependency.name,
            version=latest_stable_release_number,
            registry_name=dependency.registry_name,
        )
        logger.info(f"Latest version for dependency '{dependency.name}' fetched in registry '{corrected_registry_name}' is '{latest_stable_release_number}'.")

        latest_compatible_version_dependency: Dependency | None = None

        current_version = semver.VersionInfo.parse(dependency.version.lstrip("^~<>="))
        for i in range(len(data['versions']) - 1, -1, -1):
            try:
                iter_version = semver.VersionInfo.parse(data['versions'][i]['number'])
            except ValueError:
                logger.warning(f"Skipping invalid version '{data['versions'][i]['number']}' for dependency '{dependency.name}' in registry '{corrected_registry_name}'.")
                continue

            if iter_version.major == current_version.major:
                latest_compatible_version_dependency = Dependency(
                    name=dependency.name,
                    version=data['versions'][i]['number'],
                    registry_name=dependency.registry_name,
                )
                logger.info(f"Latest compatible version for dependency '{dependency.name}' with version '{dependency.version}' in registry '{corrected_registry_name}' is '{latest_compatible_version_dependency.version}'.")
                break
        # TODO: Sometimes this throws an error because `latest_compatible_version_dependency` is not defined/assigned.
        # The root reason for that is the LLM is hullicinating and providing a version that does not even exist in the registry.
        # We need to handle this case.
        # Maybe make the latest_compatible_version_dependency optional
        #   Or
        # Set the latest_compatible_version_dependency to the current version
        
        # !!!! BUT
        # Keep in mind that if there is no compatible version, it means even the current version does not exist in the registry.
        # So the best absolute solution is to ignore this dependency altogether and not provide any update plan for it.

        if latest_compatible_version_dependency is None:
            logger.error(f"No compatible version found for dependency '{dependency.name}' with version '{dependency.version}' in registry '{corrected_registry_name}'.")
            raise ValueError(f"No compatible version found for dependency '{dependency.name}' with version '{dependency.version}' in registry '{corrected_registry_name}'.")

        return latest_compatible_version_dependency, latest_version_dependency
