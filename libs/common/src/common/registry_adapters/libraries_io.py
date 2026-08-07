import os
import httpx
from typing import Dict, Any
from common.registry_adapters.base import BaseRegistryAdapter

class LibrariesIORegistryAdapter(BaseRegistryAdapter):
    """
    Adaptateur pour la plateforme Libraries.io (libraries.io/api).
    Permet la résolution multi-écosystèmes et intègre un fallback direct en cas de limite de taux API.
    """

    def __init__(self, platform: str = "pypi", timeout: float = 10.0):
        self.platform = platform.lower()
        self.timeout = timeout
        self.base_url = "https://libraries.io/api"
        self.api_key = os.getenv("LIBRARIES_IO_API_KEY", None)

    async def get_latest_version(self, package_name: str) -> Dict[str, Any]:
        safe_name = package_name.replace("/", "%2F")
        url = f"{self.base_url}/{self.platform}/{safe_name}"
        params = {}
        if self.api_key:
            params["api_key"] = self.api_key

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.get(url, params=params)
                if response.status_code == 200:
                    data = response.json()
                    latest_version = data.get("latest_release_number") or (data.get("latest_stable_release") or {}).get("number")
                    license_info = data.get("normalized_licenses", [None])[0] if data.get("normalized_licenses") else data.get("license")
                    stars = data.get("stars")
                    if latest_version:
                        return {
                            "name": package_name,
                            "latest_version": latest_version,
                            "license": license_info,
                            "stars": stars,
                            "registry_name": "Libraries.io",
                            "error": None
                        }
            except Exception:
                pass

            # Fallback direct vers les registres officiels si Libraries.io est en rate-limit
            try:
                if self.platform in ["pypi", "python", "pip"]:
                    fallback_res = await client.get(f"https://pypi.org/pypi/{package_name}/json")
                    if fallback_res.status_code == 200:
                        fb_data = fallback_res.json()
                        return {
                            "name": package_name,
                            "latest_version": fb_data.get("info", {}).get("version"),
                            "license": fb_data.get("info", {}).get("license"),
                            "registry_name": "PyPI (Fallback)",
                            "error": None
                        }
                elif self.platform in ["npm", "node", "javascript", "typescript"]:
                    fallback_res = await client.get(f"https://registry.npmjs.org/{safe_name}")
                    if fallback_res.status_code == 200:
                        fb_data = fallback_res.json()
                        latest = fb_data.get("dist-tags", {}).get("latest")
                        return {
                            "name": package_name,
                            "latest_version": latest,
                            "license": fb_data.get("license"),
                            "registry_name": "npm (Fallback)",
                            "error": None
                        }
            except Exception as e:
                pass

            return {
                "name": package_name,
                "latest_version": None,
                "license": None,
                "registry_name": "Libraries.io",
                "error": "Impossible de déterminer la version"
            }
