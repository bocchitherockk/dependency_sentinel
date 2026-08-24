from logging import Logger
from common.logging.global_logger import get_global_logger

from registry_service.registry_adapters.base_registry_adapter import BaseRegistryAdapter
from registry_service.registry_adapters.libraries_io_registry_adapter import LibrariesIORegistryAdapter

logger: Logger = get_global_logger(__name__)

class RegistrySelector:
    all_registry_adapters: list[type[BaseRegistryAdapter]] = [
        LibrariesIORegistryAdapter,
    ]

    # Cache to store the mapping of registry names to their corresponding adapter classes
    # This avoids repeated lookups and improves performance when selecting adapters for already fetched registries.
    registry_adapters_cache: dict[str, type[BaseRegistryAdapter]] = {}

    @staticmethod
    def get_adapter(registry_name: str) -> type[BaseRegistryAdapter]:
        registry_name = registry_name.strip().lower()
        if registry_name in RegistrySelector.registry_adapters_cache.keys():
            logger.info(f"Adapter {RegistrySelector.registry_adapters_cache[registry_name].__name__} for registry '{registry_name}' fetched from cache.")
            return RegistrySelector.registry_adapters_cache[registry_name]
        else:
            for adapter_class in RegistrySelector.all_registry_adapters:
                supported_registries: list[str] = adapter_class.get_supported_registries()
                for supported_registry in supported_registries:
                    if registry_name == supported_registry.lower():
                        logger.info(f"Adapter {adapter_class.__name__} for registry '{registry_name}' fetched.")
                        RegistrySelector.registry_adapters_cache[registry_name] = adapter_class
                        return adapter_class
            logger.error(f'No adapter found for registry: {registry_name}. Supported registries: {list(RegistrySelector.registry_adapters_cache.keys())}')
            raise ValueError(f'No adapter found for registry: {registry_name}. Supported registries: {list(RegistrySelector.registry_adapters_cache.keys())}')

logger.info(f'RegistrySelector initialized with {len(RegistrySelector.all_registry_adapters)} registry adapters.')
logger.debug(f'Supported registry adapters: {[adapter.__name__ for adapter in RegistrySelector.all_registry_adapters]}')
