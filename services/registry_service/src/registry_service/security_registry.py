import httpx

from common.schemas.Dependency import Dependency
from common.schemas.VulnerabilityItem import VulnerabilityItem

class SecurityRegistry:
    ecosystems_url: str = 'https://storage.googleapis.com/osv-vulnerabilities/ecosystems.txt'
    osv_url: str = 'https://api.osv.dev/v1/query'

    supported_ecosystems: list[str] | None = None

    @staticmethod
    def get_supported_ecosystems() -> list[str]:
        if SecurityRegistry.supported_ecosystems is None:
            # Note:
            # Fetch the supported ecosystems from the OSV.dev service
            # I am using a synchronous request here because this method is expected to be called only once during the lifetime of the application
            # And in it of itself is not a heavy time-consuming operation, so it should not block the event loop for too long
            response = httpx.get(SecurityRegistry.ecosystems_url)
            SecurityRegistry.supported_ecosystems = [
                ecosystem
                for ecosystem in response.text.splitlines()
                if ecosystem != '[EMPTY]'
            ]
        return SecurityRegistry.supported_ecosystems

    @staticmethod
    def correct_ecosystem_name(ecosystem: str) -> str:
        for supported_ecosystem in SecurityRegistry.get_supported_ecosystems():
            if supported_ecosystem.lower() == ecosystem.lower():
                return supported_ecosystem
        raise ValueError(f"Ecosystem '{ecosystem}' is not supported by OSV.dev. Supported ecosystems: {SecurityRegistry.supported_ecosystems}")

    @staticmethod
    async def query_vulnerabilities(dependency: Dependency) -> list[VulnerabilityItem]:
        payload = {
            'package': {
                'name': dependency.name,
                'ecosystem': SecurityRegistry.correct_ecosystem_name(dependency.registry.name)
            },
            'version': dependency.version
        }

        async with httpx.AsyncClient(timeout=None) as client:
            response = await client.post(SecurityRegistry.osv_url, json=payload)

        response.raise_for_status()
        vulns = response.json().get('vulns', [])
        result: list[VulnerabilityItem] = [
            VulnerabilityItem(
                id=vuln['id'],
                summary=vuln['summary'],
                details=vuln['details'],
                severity=vuln['database_specific']['severity'],
                aliases=vuln['aliases'],
            )
            for vuln in vulns
        ]
        return result
