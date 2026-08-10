from abc import ABC, abstractmethod

from common.schemas.Dependency import Dependency

class BaseRegistryAdapter(ABC):
    supported_registries: list[str] | None = None

    @staticmethod
    @abstractmethod
    def get_supported_registries() -> list[str]:
        pass

    @staticmethod
    @abstractmethod
    def correct_registry_name(registry_name: str) -> str:
        pass

    @staticmethod
    @abstractmethod
    async def get_all_versions(dependency: Dependency) -> list[Dependency]:
        pass

    @staticmethod
    @abstractmethod
    async def get_latest_version(dependency: Dependency) -> Dependency:
        pass
