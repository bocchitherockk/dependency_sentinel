import os
from typing import override

import httpx
import semver
from dotenv import load_dotenv

from common.schemas.Dependency import Dependency
from registry_service.registry_adapters.base_registry_adapter import BaseRegistryAdapter

load_dotenv()

class LibrariesIORegistryAdapter(BaseRegistryAdapter):
    base_url: str = 'https://libraries.io/api'
    api_key:  str = os.getenv('LIBRARIES_IO_API_KEY', None)

    @override
    @staticmethod
    def get_supported_registries() -> list[str]:
        if LibrariesIORegistryAdapter.supported_registries is None:
            url: str = f'{LibrariesIORegistryAdapter.base_url}/platforms'
            params = {'api_key': LibrariesIORegistryAdapter.api_key} if LibrariesIORegistryAdapter.api_key is not None else {}
            response = httpx.get(url, params=params, timeout=None)
            response.raise_for_status()
            data = response.json()
            LibrariesIORegistryAdapter.supported_registries = [platform['name'] for platform in data]
        return LibrariesIORegistryAdapter.supported_registries

    @override
    @staticmethod
    def correct_registry_name(registry_name: str) -> str:
        for supported_registry in LibrariesIORegistryAdapter.get_supported_registries():
            if supported_registry.lower() == registry_name.lower():
                return supported_registry
        raise ValueError(f"Registry '{registry_name}' is not supported by Libraries.io. Supported registries: {LibrariesIORegistryAdapter.supported_registries}")

    @override
    @staticmethod
    async def get_all_versions_dependencies(dependency: Dependency) -> list[Dependency]:
        safe_dependency_name: str = dependency.name.replace('/', '%2F')
        corrected_registry_name: str = LibrariesIORegistryAdapter.correct_registry_name(dependency.registry.name)
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
        return result

    @override
    @staticmethod
    async def get_latest_version_dependency(dependency: Dependency) -> Dependency:
        safe_dependency_name: str = dependency.name.replace('/', '%2F')
        corrected_registry_name: str = LibrariesIORegistryAdapter.correct_registry_name(dependency.registry.name)
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
        return latest_version_dependency

    @override
    @staticmethod
    async def get_latest_compatible_version_dependency(dependency: Dependency) -> Dependency:
        safe_dependency_name: str = dependency.name.replace('/', '%2F')
        corrected_registry_name: str = LibrariesIORegistryAdapter.correct_registry_name(dependency.registry.name)
        url: str = f'{LibrariesIORegistryAdapter.base_url}/{corrected_registry_name}/{safe_dependency_name}'
        params = {'api_key': LibrariesIORegistryAdapter.api_key} if LibrariesIORegistryAdapter.api_key is not None else {}

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
                    registry=dependency.registry,
                )
                return latest_compatible_version_dependency
        
        raise ValueError(f"No compatible version found for dependency '{dependency.name}' with version '{dependency.version}' in registry '{dependency.registry.name}'.")

    @override
    @staticmethod
    async def get_candidate_versions_dependencies(dependency: Dependency) -> tuple[Dependency, Dependency]:
        safe_dependency_name: str = dependency.name.replace('/', '%2F')
        corrected_registry_name: str = LibrariesIORegistryAdapter.correct_registry_name(dependency.registry.name)
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

        current_version = semver.VersionInfo.parse(dependency.version.lstrip("^~<>="))
        for i in range(len(data['versions']) - 1, -1, -1):
            iter_version = semver.VersionInfo.parse(data['versions'][i]['number'])
            if iter_version.major == current_version.major:
                latest_compatible_version_dependency: Dependency = Dependency(
                    name=dependency.name,
                    version=data['versions'][i]['number'],
                    registry=dependency.registry,
                )
                break
        return latest_compatible_version_dependency, latest_version_dependency
