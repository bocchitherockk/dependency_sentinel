from abc import ABC, abstractmethod
from typing import Optional, Dict, Any

class BaseRegistryAdapter(ABC):
    """
    Interface abstraite pour tous les adaptateurs de registres de dépendances.
    """

    @abstractmethod
    async def get_latest_version(self, package_name: str) -> Dict[str, Any]:
        """
        Récupère la dernière version disponible pour un paquet donné.
        Retourne un dictionnaire contenant :
        - name: str
        - latest_version: str
        - release_date: Optional[str]
        - license: Optional[str]
        - registry_name: str
        """
        pass
