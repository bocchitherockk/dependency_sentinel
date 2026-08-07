from typing import Optional
from common.registry_adapters.base import BaseRegistryAdapter
from common.registry_adapters.libraries_io import LibrariesIORegistryAdapter

class RegistryAdapterFactory:
    """
    Fabrique (Factory Pattern) centralisée sur Libraries.io pour la résolution multi-écosystèmes.
    """

    @staticmethod
    def get_adapter(registry_name_or_ecosystem: str) -> BaseRegistryAdapter:
        ecosystem_clean = (registry_name_or_ecosystem or "").strip().lower()

        if ecosystem_clean in ["pypi", "python", "pip"]:
            return LibrariesIORegistryAdapter(platform="pypi")
        elif ecosystem_clean in ["npm", "node", "javascript", "typescript"]:
            return LibrariesIORegistryAdapter(platform="npm")
        elif ecosystem_clean in ["maven", "maven central", "java"]:
            return LibrariesIORegistryAdapter(platform="maven")
        elif ecosystem_clean in ["docker", "dockerhub", "docker hub", "container"]:
            return LibrariesIORegistryAdapter(platform="docker")
        elif ecosystem_clean in ["cargo", "rust"]:
            return LibrariesIORegistryAdapter(platform="cargo")
        elif ecosystem_clean in ["rubygems", "ruby"]:
            return LibrariesIORegistryAdapter(platform="rubygems")
        elif ecosystem_clean in ["packagist", "php"]:
            return LibrariesIORegistryAdapter(platform="packagist")
        elif ecosystem_clean in ["nuget", "c#", ".net"]:
            return LibrariesIORegistryAdapter(platform="nuget")
        else:
            # Fallback par défaut sur Libraries.io avec la plateforme demandée ou pypi
            platform = ecosystem_clean if ecosystem_clean else "pypi"
            return LibrariesIORegistryAdapter(platform=platform)
