import asyncio

import httpx
import pytest

from common.schemas.Dependency import Dependency
from common.schemas.Registry import Registry
from registry_service.registry_adapters.libraries_io_registry_adapter import LibrariesIORegistryAdapter


class MockResponse:
    def __init__(self, *, json_data=None):
        self._json_data = json_data
    def raise_for_status(self) -> None:
        return None
    def json(self):
        return self._json_data


class MockAsyncClient:
    def __init__(self, response: MockResponse):
        self.response = response
        self.calls: list[dict] = []
    async def __aenter__(self):
        return self
    async def __aexit__(self, exc_type, exc, tb):
        return None
    async def get(self, url: str, params=None):
        self.calls.append({"method": "get", "url": url, "params": params})
        return self.response


def test_libraries_io_supported_registries_are_cached(monkeypatch):
    LibrariesIORegistryAdapter.supported_registries = None
    monkeypatch.setattr(LibrariesIORegistryAdapter, "api_key", "test-api-key")

    calls: list[dict] = []

    def fake_get(url, params=None, timeout=None):
        calls.append({"url": url, "params": params, "timeout": timeout})
        return MockResponse(json_data=[{"name": "PyPI"}, {"name": "npm"}])

    monkeypatch.setattr(httpx, "get", fake_get)

    first = LibrariesIORegistryAdapter.get_supported_registries()
    second = LibrariesIORegistryAdapter.get_supported_registries()

    assert first == ["PyPI", "npm"]
    assert second == ["PyPI", "npm"]
    assert calls == [
        {
            "url": "https://libraries.io/api/platforms",
            "params": {"api_key": "test-api-key"},
            "timeout": None,
        }
    ]


def test_libraries_io_correct_registry_name_is_case_insensitive(monkeypatch):
    monkeypatch.setattr(
        LibrariesIORegistryAdapter,
        "get_supported_registries",
        staticmethod(lambda: ["PyPI", "npm"]),
    )

    assert LibrariesIORegistryAdapter.correct_registry_name("pypi") == "PyPI"
    assert LibrariesIORegistryAdapter.correct_registry_name("NPM") == "npm"


def test_libraries_io_correct_registry_name_rejects_unknown(monkeypatch):
    monkeypatch.setattr(
        LibrariesIORegistryAdapter,
        "get_supported_registries",
        staticmethod(lambda: ["PyPI"]),
    )

    with pytest.raises(ValueError, match="Registry 'unknown' is not supported"):
        LibrariesIORegistryAdapter.correct_registry_name("unknown")


def test_libraries_io_get_all_versions_builds_expected_dependencies(monkeypatch):
    dependency = Dependency(
        name="scope/name",
        version="1.0.0",
        registry=Registry(name="npm", url="https://example.invalid"),
    )
    client = MockAsyncClient(MockResponse(json_data={"versions": [{"number": "1.0.1"}, {"number": "2.0.0"}]}))

    monkeypatch.setattr(LibrariesIORegistryAdapter, "api_key", "test-api-key")
    monkeypatch.setattr(LibrariesIORegistryAdapter, "correct_registry_name", staticmethod(lambda name: "npm"))
    monkeypatch.setattr(httpx, "AsyncClient", lambda timeout=None: client)

    versions = asyncio.run(LibrariesIORegistryAdapter.get_all_versions(dependency))

    assert [item.version for item in versions] == ["1.0.1", "2.0.0"]
    assert all(item.name == dependency.name for item in versions)
    assert all(item.registry == dependency.registry for item in versions)
    assert client.calls == [
        {
            "method": "get",
            "url": "https://libraries.io/api/npm/scope%2Fname",
            "params": {"api_key": "test-api-key"},
        }
    ]


def test_libraries_io_get_latest_version_returns_latest_release(monkeypatch):
    dependency = Dependency(
        name="scope/name",
        version="1.0.0",
        registry=Registry(name="npm", url="https://example.invalid"),
    )
    client = MockAsyncClient(MockResponse(json_data={"latest_stable_release_number": "2.3.4"}))

    monkeypatch.setattr(LibrariesIORegistryAdapter, "api_key", "test-api-key")
    monkeypatch.setattr(LibrariesIORegistryAdapter, "correct_registry_name", staticmethod(lambda name: "npm"))
    monkeypatch.setattr(httpx, "AsyncClient", lambda timeout=None: client)

    latest = asyncio.run(LibrariesIORegistryAdapter.get_latest_version(dependency))

    assert latest.name == dependency.name
    assert latest.version == "2.3.4"
    assert latest.registry == dependency.registry
    assert client.calls == [
        {
            "method": "get",
            "url": "https://libraries.io/api/npm/scope%2Fname",
            "params": {"api_key": "test-api-key"},
        }
    ]
