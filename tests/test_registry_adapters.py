import pytest
from common.registry_adapters.factory import RegistryAdapterFactory
from common.registry_adapters.libraries_io import LibrariesIORegistryAdapter

def test_registry_adapter_factory():
    assert isinstance(RegistryAdapterFactory.get_adapter("PyPI"), LibrariesIORegistryAdapter)
    assert isinstance(RegistryAdapterFactory.get_adapter("npm"), LibrariesIORegistryAdapter)
    assert isinstance(RegistryAdapterFactory.get_adapter("Maven Central"), LibrariesIORegistryAdapter)
    assert isinstance(RegistryAdapterFactory.get_adapter("Docker Hub"), LibrariesIORegistryAdapter)
    assert isinstance(RegistryAdapterFactory.get_adapter("libraries_io"), LibrariesIORegistryAdapter)

@pytest.mark.anyio
async def test_libraries_io_pypi_adapter():
    adapter = RegistryAdapterFactory.get_adapter("pypi")
    res = await adapter.get_latest_version("requests")
    assert res["name"] == "requests"
    assert res["latest_version"] is not None
    assert "registry_name" in res

@pytest.mark.anyio
async def test_libraries_io_npm_adapter():
    adapter = RegistryAdapterFactory.get_adapter("npm")
    res = await adapter.get_latest_version("express")
    assert res["name"] == "express"
    assert res["latest_version"] is not None
    assert "registry_name" in res
