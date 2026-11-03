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
    api_key:  str | None = os.getenv('LIBRARIES_IO_API_KEY') or None
    # normally this should be 60 requests per minute
    # but `get_supported_registries()` is not an async function, meaning we can't call `await rate_limiter.acquire()` in it
    # so we can't use the rate limiter in it.
    # Therefore, we will use a lower rate limit of 59 requests per minute to avoid hitting the rate limit of 60 requests per minute in edge cases.
    rate_limiter: RateLimiter = RateLimiter(max_rate=59, time_window=60.0)

    _supported_registries_lock = threading.Lock()

    @override
    @staticmethod
    def get_supported_registries() -> list[str]:
        return [
            'NPM', 'Maven', 'PyPI', 'Rubygems', 'Packagist', 'NuGet',
            'Cargo', 'Go', 'Hex', 'Bower', 'CocoaPods', 'Clojars', 'Pub'
        ]

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

        async def limit_redirects(response):
            if response.is_redirect:
                logger.info(f"Received redirect response for dependency '{dependency.name}' in registry '{corrected_registry_name}'.")
                logger.debug(f'Original URL: {response.request.url}, Redirected URL: {response.headers.get("location")}')
                await LibrariesIORegistryAdapter.rate_limiter.acquire()

        await LibrariesIORegistryAdapter.rate_limiter.acquire()
        async with httpx.AsyncClient(
            timeout=None,
            follow_redirects=True,
            event_hooks={'response': [limit_redirects]},
        ) as client:
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
    async def get_latest_version_dependency(dependency: Dependency) -> Dependency | None:
        safe_dependency_name: str = dependency.name.replace('/', '%2F')
        corrected_registry_name: str = LibrariesIORegistryAdapter.correct_registry_name(dependency.registry_name)
        url: str = f'{LibrariesIORegistryAdapter.base_url}/{corrected_registry_name}/{safe_dependency_name}'
        params = {'api_key': LibrariesIORegistryAdapter.api_key} if LibrariesIORegistryAdapter.api_key is not None else {}

        async def limit_redirects(response):
            if response.is_redirect:
                logger.info(f"Received redirect response for dependency '{dependency.name}' in registry '{corrected_registry_name}'.")
                logger.debug(f'Original URL: {response.request.url}, Redirected URL: {response.headers.get("location")}')
                await LibrariesIORegistryAdapter.rate_limiter.acquire()

        await LibrariesIORegistryAdapter.rate_limiter.acquire()
        async with httpx.AsyncClient(
            timeout=None,
            follow_redirects=True,
            event_hooks={'response': [limit_redirects]},
        ) as client:
            response = await client.get(url, params=params)

        response.raise_for_status()
        data = response.json()
        latest_stable_release_number: str | None = data['latest_stable_release_number']
        if latest_stable_release_number is None:
            logger.warning(f"Latest stable release number is null for dependency '{dependency.name}' in registry '{corrected_registry_name}'.")
            return None

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

        async def limit_redirects(response):
            if response.is_redirect:
                logger.info(f"Received redirect response for dependency '{dependency.name}' in registry '{corrected_registry_name}'.")
                logger.debug(f'Original URL: {response.request.url}, Redirected URL: {response.headers.get("location")}')
                await LibrariesIORegistryAdapter.rate_limiter.acquire()

        await LibrariesIORegistryAdapter.rate_limiter.acquire()
        async with httpx.AsyncClient(
            timeout=None,
            follow_redirects=True,
            event_hooks={'response': [limit_redirects]},
        ) as client:
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
    async def get_candidate_versions_dependencies(dependency: Dependency) -> tuple[Dependency | None, Dependency | None]:
        registry_upper = (dependency.registry_name or '').upper()

        # 1. Direct NPM registry fetch (faster, no rate limit, no api key required)
        if registry_upper == 'NPM':
            try:
                safe_name = dependency.name
                async with httpx.AsyncClient(timeout=15.0) as client:
                    resp = await client.get(f'https://registry.npmjs.org/{safe_name}')
                if resp.status_code == 200:
                    data = resp.json()
                    latest_str = data.get('dist-tags', {}).get('latest')
                    versions_list = list(data.get('versions', {}).keys())

                    latest_dep = Dependency(name=dependency.name, version=latest_str, registry_name=dependency.registry_name) if latest_str else None
                    latest_comp_dep = None
                    try:
                        curr_v = semver.VersionInfo.parse(dependency.version.lstrip('^~<>='))
                        for v_str in reversed(versions_list):
                            try:
                                p = semver.VersionInfo.parse(v_str)
                                if p.major == curr_v.major:
                                    latest_comp_dep = Dependency(name=dependency.name, version=v_str, registry_name=dependency.registry_name)
                                    break
                            except ValueError:
                                continue
                    except ValueError:
                        pass
                    logger.info(f'[NPM Direct] Candidate versions for {dependency.name}: comp={latest_comp_dep.version if latest_comp_dep else None}, latest={latest_dep.version if latest_dep else None}')
                    return latest_comp_dep, latest_dep
            except Exception as e:
                logger.warning(f'[NPM Direct] Query failed for {dependency.name}: {e}')

        # 2. Direct Maven Central search fetch
        if registry_upper == 'MAVEN':
            try:
                if ':' in dependency.name:
                    g, a = dependency.name.split(':', 1)
                    q = f'g:{g} AND a:{a}'
                else:
                    q = f'a:{dependency.name}'
                async with httpx.AsyncClient(timeout=15.0) as client:
                    resp = await client.get('https://search.maven.org/solrsearch/select', params={'q': q, 'core': 'gav', 'rows': 100, 'wt': 'json'})
                if resp.status_code == 200:
                    data = resp.json()
                    docs = data.get('response', {}).get('docs', [])
                    versions_list = [doc['v'] for doc in docs]

                    latest_str = None
                    latest_comp_str = None
                    try:
                        curr_v = semver.VersionInfo.parse(dependency.version.lstrip('^~<>='))
                        for v_str in versions_list:
                            try:
                                p = semver.VersionInfo.parse(v_str)
                                if not p.prerelease:
                                    if latest_str is None:
                                        latest_str = v_str
                                    if p.major == curr_v.major and latest_comp_str is None:
                                        latest_comp_str = v_str
                            except ValueError:
                                continue
                    except ValueError:
                        if versions_list:
                            latest_str = versions_list[0]

                    latest_dep = Dependency(name=dependency.name, version=latest_str, registry_name=dependency.registry_name) if latest_str else None
                    latest_comp_dep = Dependency(name=dependency.name, version=latest_comp_str, registry_name=dependency.registry_name) if latest_comp_str else None
                    logger.info(f'[Maven Direct] Candidate versions for {dependency.name}: comp={latest_comp_dep.version if latest_comp_dep else None}, latest={latest_dep.version if latest_dep else None}')
                    return latest_comp_dep, latest_dep
            except Exception as e:
                logger.warning(f'[Maven Direct] Query failed for {dependency.name}: {e}')

        # 3. Direct PyPI fetch
        if registry_upper == 'PYPI':
            try:
                async with httpx.AsyncClient(timeout=15.0) as client:
                    resp = await client.get(f'https://pypi.org/pypi/{dependency.name}/json')
                if resp.status_code == 200:
                    data = resp.json()
                    latest_str = data.get('info', {}).get('version')
                    versions_list = list(data.get('releases', {}).keys())
                    latest_dep = Dependency(name=dependency.name, version=latest_str, registry_name=dependency.registry_name) if latest_str else None
                    latest_comp_dep = None
                    try:
                        curr_v = semver.VersionInfo.parse(dependency.version.lstrip('^~<>='))
                        for v_str in reversed(versions_list):
                            try:
                                p = semver.VersionInfo.parse(v_str)
                                if p.major == curr_v.major:
                                    latest_comp_dep = Dependency(name=dependency.name, version=v_str, registry_name=dependency.registry_name)
                                    break
                            except ValueError:
                                continue
                    except ValueError:
                        pass
                    logger.info(f'[PyPI Direct] Candidate versions for {dependency.name}: comp={latest_comp_dep.version if latest_comp_dep else None}, latest={latest_dep.version if latest_dep else None}')
                    return latest_comp_dep, latest_dep
            except Exception as e:
                logger.warning(f'[PyPI Direct] Query failed for {dependency.name}: {e}')

        # 4. Fallback to Libraries.io
        try:
            safe_dependency_name: str = dependency.name.replace('/', '%2F')
            corrected_registry_name: str = LibrariesIORegistryAdapter.correct_registry_name(dependency.registry_name)
            url: str = f'{LibrariesIORegistryAdapter.base_url}/{corrected_registry_name}/{safe_dependency_name}'
            params = {'api_key': LibrariesIORegistryAdapter.api_key} if LibrariesIORegistryAdapter.api_key else {}

            async def limit_redirects(response):
                if response.is_redirect:
                    await LibrariesIORegistryAdapter.rate_limiter.acquire()

            await LibrariesIORegistryAdapter.rate_limiter.acquire()
            async with httpx.AsyncClient(
                timeout=15.0,
                follow_redirects=True,
                event_hooks={'response': [limit_redirects]},
            ) as client:
                response = await client.get(url, params=params)

            if response.status_code != 200:
                logger.warning(f'Libraries.io returned status {response.status_code} for dependency {dependency.name}.')
                return None, None

            data = response.json()
            latest_stable_release_number: str | None = data.get('latest_stable_release_number')
            latest_version_dependency: Dependency | None = None
            if latest_stable_release_number:
                latest_version_dependency = Dependency(
                    name=dependency.name,
                    version=latest_stable_release_number,
                    registry_name=dependency.registry_name,
                )

            try:
                current_version = semver.VersionInfo.parse(dependency.version.lstrip('^~<>='))
            except ValueError:
                return None, latest_version_dependency

            versions = data.get('versions', [])
            for i in range(len(versions) - 1, -1, -1):
                try:
                    iter_version = semver.VersionInfo.parse(versions[i]['number'])
                except ValueError:
                    continue

                if iter_version.major == current_version.major:
                    latest_compatible_version_dependency = Dependency(
                        name=dependency.name,
                        version=versions[i]['number'],
                        registry_name=dependency.registry_name,
                    )
                    return latest_compatible_version_dependency, latest_version_dependency

            return None, latest_version_dependency
        except Exception as e:
            logger.warning(f'Error querying candidate versions for {dependency.name}: {e}')
            return None, None
