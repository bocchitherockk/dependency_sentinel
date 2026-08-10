import pytest

from registry_service.registry_adapters.libraries_io_registry_adapter import LibrariesIORegistryAdapter
from registry_service.registry_selector import RegistrySelector


def test_registry_selector_resolves_and_caches_adapter(monkeypatch):
    RegistrySelector.registry_adapters.clear()
    monkeypatch.setattr(LibrariesIORegistryAdapter, "get_supported_registries", staticmethod(lambda: ["PyPI"]))

    adapter = RegistrySelector.get_adapter(" pypi ")

    assert adapter is LibrariesIORegistryAdapter
    assert RegistrySelector.registry_adapters["pypi"] is LibrariesIORegistryAdapter


def test_registry_selector_rejects_unknown_registry(monkeypatch):
    RegistrySelector.registry_adapters.clear()
    monkeypatch.setattr(LibrariesIORegistryAdapter, "get_supported_registries", staticmethod(lambda: ["PyPI"]))

    with pytest.raises(ValueError, match="No adapter found for registry: unknown"):
        RegistrySelector.get_adapter("unknown")
