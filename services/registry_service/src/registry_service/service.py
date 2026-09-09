from logging import Logger

from common.logging.global_logger import get_global_logger

from registry_service.registry_selector import RegistrySelector


logger: Logger = get_global_logger(__name__)

def get_supported_registries_service() -> list[str]:
    registries: list[str] = []
    for registry_adapter in RegistrySelector.all_registry_adapters:
        registries.extend(registry_adapter.get_supported_registries())
    logger.info(f"All supported registries: {registries}")
    return registries
