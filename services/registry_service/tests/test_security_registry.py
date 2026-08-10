import asyncio

import httpx

from common.schemas.Dependency import Dependency
from common.schemas.Registry import Registry
from registry_service.security_registry import SecurityRegistry


class MockResponse:
    def __init__(self, *, json_data=None, text: str = ""):
        self._json_data = json_data
        self.text = text
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
    async def post(self, url: str, json=None):
        self.calls.append({"method": "post", "url": url, "json": json})
        return self.response


def test_security_registry_filters_empty_ecosystem_and_caches(monkeypatch):
    SecurityRegistry.supported_ecosystems = None

    monkeypatch.setattr(httpx, "get", lambda url: MockResponse(text="PyPI\n[EMPTY]\nnpm\n"))

    ecosystems = SecurityRegistry.get_supported_ecosystems()
    cached = SecurityRegistry.get_supported_ecosystems()

    assert ecosystems == ["PyPI", "npm"]
    assert cached == ["PyPI", "npm"]


def test_security_registry_correct_ecosystem_name(monkeypatch):
    monkeypatch.setattr(SecurityRegistry, "get_supported_ecosystems", staticmethod(lambda: ["PyPI", "npm"]))

    assert SecurityRegistry.correct_ecosystem_name("pypi") == "PyPI"
    assert SecurityRegistry.correct_ecosystem_name("NPM") == "npm"


def test_security_registry_correct_ecosystem_name_rejects_unknown(monkeypatch):
    monkeypatch.setattr(SecurityRegistry, "get_supported_ecosystems", staticmethod(lambda: ["PyPI"]))

    try:
        SecurityRegistry.correct_ecosystem_name("unknown")
    except ValueError as error:
        assert "Ecosystem 'unknown' is not supported" in str(error)
    else:
        raise AssertionError("expected ValueError")


def test_security_registry_query_vulnerabilities_maps_response(monkeypatch):
    client = MockAsyncClient(
        MockResponse(
            json_data={
                "vulns": [
                    {
                        "id": "CVE-2024-0001",
                        "summary": "Example summary",
                        "details": "Example details",
                        "database_specific": {"severity": "HIGH"},
                        "aliases": ["GHSA-xxxx"],
                    }
                ]
            }
        )
    )

    monkeypatch.setattr(SecurityRegistry, "correct_ecosystem_name", staticmethod(lambda ecosystem: "PyPI"))
    monkeypatch.setattr(httpx, "AsyncClient", lambda timeout=None: client)

    vulnerabilities = asyncio.run(
        SecurityRegistry.query_vulnerabilities(
            Dependency(
                name="requests",
                version="2.31.0",
                registry=Registry(name="pypi", url="https://example.invalid"),
            )
        )
    )

    assert len(vulnerabilities) == 1
    assert vulnerabilities[0].id == "CVE-2024-0001"
    assert vulnerabilities[0].severity == "HIGH"
    assert client.calls == [
        {
            "method": "post",
            "url": "https://api.osv.dev/v1/query",
            "json": {
                "package": {"name": "requests", "ecosystem": "PyPI"},
                "version": "2.31.0",
            },
        }
    ]
