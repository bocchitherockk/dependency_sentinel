import os
from typing import override
from logging import Logger
import threading

import httpx
import semver
from dotenv import load_dotenv

from common.logging.global_logger import get_global_logger
from common.schemas.Dependency import Dependency
from common.rate_limiter.RateLimiter import RateLimiter
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
    # normally this should be 60 requests per minute
    # but `get_supported_registries()` is not an async function, meaning we can't call `await rate_limiter.acquire()` in it
    # so we can't use the rate limiter in it.
    # Therefore, we will use a lower rate limit of 59 requests per minute to avoid hitting the rate limit of 60 requests per minute in edge cases.
    rate_limiter: RateLimiter = RateLimiter(max_rate=59, time_window=60.0)

    _supported_registries_lock = threading.Lock()

    @override
    @staticmethod
    def get_supported_registries() -> list[str]:
        with LibrariesIORegistryAdapter._supported_registries_lock:
            if LibrariesIORegistryAdapter._supported_registries is None:
                url: str = f'{LibrariesIORegistryAdapter.base_url}/platforms'
                params = { 'api_key': LibrariesIORegistryAdapter.api_key } if LibrariesIORegistryAdapter.api_key is not None else {}
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

        await LibrariesIORegistryAdapter.rate_limiter.acquire()
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

        await LibrariesIORegistryAdapter.rate_limiter.acquire()
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
    async def get_latest_compatible_version_dependency(dependency: Dependency) -> Dependency | None:
        safe_dependency_name: str = dependency.name.replace('/', '%2F')
        corrected_registry_name: str = LibrariesIORegistryAdapter.correct_registry_name(dependency.registry_name)
        url: str = f'{LibrariesIORegistryAdapter.base_url}/{corrected_registry_name}/{safe_dependency_name}'
        params = { 'api_key': LibrariesIORegistryAdapter.api_key } if LibrariesIORegistryAdapter.api_key is not None else {}

        await LibrariesIORegistryAdapter.rate_limiter.acquire()
        async with httpx.AsyncClient(timeout=None) as client:
            response = await client.get(url, params=params)

        response.raise_for_status()
        data = response.json()

        try:
            # TODO: this is a quick workaround to get the exact version
            current_version = semver.VersionInfo.parse(dependency.version.lstrip("^~<>="))
        except ValueError:
            # In this case, we return None.
            logger.error(f"Invalid Semver for current version '{dependency.version}' for dependency '{dependency.name}' in registry '{corrected_registry_name}'.")
            return None

        # Search for the latest compatible version in the versions list
        # We iterate in reverse because the result is likely to be towards the end of the list
        for i in range(len(data['versions']) - 1, -1, -1):
            try:
                iter_version = semver.VersionInfo.parse(data['versions'][i]['number'])
            except ValueError:
                # Sometimes, the version includes some invalid characters that are not compatible with Semver.
                # In this case, we skip this version and continue to the next one in hope of finding a valid one.
                logger.warning(f"Skipping invalid version '{data['versions'][i]['number']}' for dependency '{dependency.name}' in registry '{corrected_registry_name}'.")
                continue

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
        # raise ValueError(f"No compatible version found for dependency '{dependency.name}' with version '{dependency.version}' in registry '{corrected_registry_name}'.")
        return None


    @override
    @staticmethod
    async def get_candidate_versions_dependencies(dependency: Dependency) -> tuple[Dependency, Dependency] | None:
        safe_dependency_name: str = dependency.name.replace('/', '%2F')
        corrected_registry_name: str = LibrariesIORegistryAdapter.correct_registry_name(dependency.registry_name)
        url: str = f'{LibrariesIORegistryAdapter.base_url}/{corrected_registry_name}/{safe_dependency_name}'
        params = {'api_key': LibrariesIORegistryAdapter.api_key} if LibrariesIORegistryAdapter.api_key is not None else {}

        await LibrariesIORegistryAdapter.rate_limiter.acquire()
        async with httpx.AsyncClient(timeout=None) as client:
            response = await client.get(url, params=params)

        response.raise_for_status()
        data = response.json()

        latest_stable_release_number: str = data['latest_stable_release_number']
        latest_compatible_version_dependency: Dependency | None = None
        latest_version_dependency: Dependency = Dependency(
            name=dependency.name,
            version=latest_stable_release_number,
            registry_name=dependency.registry_name,
        )
        logger.info(f"Latest version for dependency '{dependency.name}' fetched in registry '{corrected_registry_name}' is '{latest_stable_release_number}'.")

        try:
            # TODO: this is a quick workaround to get the exact version
            current_version = semver.VersionInfo.parse(dependency.version.lstrip("^~<>="))
        except ValueError:
            # In this case, we return None.
            logger.error(f"Invalid Semver for current version '{dependency.version}' for dependency '{dependency.name}' in registry '{corrected_registry_name}'.")
            return None
        
        for i in range(len(data['versions']) - 1, -1, -1):
            try:
                iter_version = semver.VersionInfo.parse(data['versions'][i]['number'])
            except ValueError:
                # Sometimes, the version includes some invalid characters that are not compatible with Semver.
                # In this case, we skip this version and continue to the next one in hope of finding a valid one.
                logger.warning(f"Skipping invalid version '{data['versions'][i]['number']}' for dependency '{dependency.name}' in registry '{corrected_registry_name}'.")
                continue

            if iter_version.major == current_version.major:
                latest_compatible_version_dependency = Dependency(
                    name=dependency.name,
                    version=data['versions'][i]['number'],
                    registry_name=dependency.registry_name,
                )
                logger.info(f"Latest compatible version for dependency '{dependency.name}' with version '{dependency.version}' in registry '{corrected_registry_name}' is '{latest_compatible_version_dependency.version}'.")
                return latest_compatible_version_dependency, latest_version_dependency
            logger.debug(f"Version '{data['versions'][i]['number']}' is not compatible with current version '{dependency.version}' for dependency '{dependency.name}' in registry '{corrected_registry_name}'.")

        # TODO: Sometimes we can't find a latest compatible version with the current version in the data['versions'].
        # Which is weird because at least the current version should be in the list of versions and act as the latest compatible version.
        # The root reason for that is the LLM is providing a wrong current version from the one in the manifest file, or the manifest file doesn't even have a version and the LLM is providing a version from it's knowledge.
        # And that version does not even exist in the registry.

        # The solution for now is return None for the latest compatible version dependency and handle that case in the caller function.
        # When we return None for the latest compatible version dependency, it means that the current version provided by the LLM is incorrect.
        # So the entire update context for this dependency is invalid and we should not provide any update plan for it.

        logger.error(f"No compatible version found for dependency '{dependency.name}' with version '{dependency.version}' in registry '{corrected_registry_name}'.")
        # raise ValueError(f"No compatible version found for dependency '{dependency.name}' with version '{dependency.version}' in registry '{corrected_registry_name}'.")
