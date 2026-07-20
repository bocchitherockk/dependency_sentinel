import types

from common.schemas.CloneRepositoryRequest import CloneRepositoryRequest

import gateway.main as main


class FakeResponse:
    def __init__(self, status_code=200, json_data=None):
        self.status_code = status_code
        self._json = json_data or {}

    def json(self):
        return self._json


def test_scan_repository_success(monkeypatch):
    # prepare fake responses for post (clone) and get (list files)
    monkeypatch.setattr(
        main, "requests",
        types.SimpleNamespace(
            post=lambda *a, **k: FakeResponse(status_code=200, json_data={"result": "cloned"}),
            get=lambda *a, **k: FakeResponse(status_code=200, json_data={"files": ["a.py", "b.txt"]}),
        ),
    )

    req = CloneRepositoryRequest(repository_url="https://example.com/repo.git")
    result = main.scan_repository(req)

    assert result == {"files": ["a.py", "b.txt"]}


def test_scan_repository_clone_failure(monkeypatch):
    # post (clone) fails with non-200
    monkeypatch.setattr(
        main, "requests",
        types.SimpleNamespace(
            post=lambda *a, **k: FakeResponse(status_code=500),
            get=lambda *a, **k: FakeResponse(status_code=200, json_data={}),
        ),
    )

    req = CloneRepositoryRequest(repository_url="https://example.com/repo.git")
    result = main.scan_repository(req)

    assert result == {"error": "Failed to clone repository"}


def test_scan_repository_get_failure(monkeypatch):
    # post succeeds but get (fetch content) fails
    monkeypatch.setattr(
        main, "requests",
        types.SimpleNamespace(
            post=lambda *a, **k: FakeResponse(status_code=200, json_data={}),
            get=lambda *a, **k: FakeResponse(status_code=404),
        ),
    )

    req = CloneRepositoryRequest(repository_url="https://example.com/repo.git")
    result = main.scan_repository(req)

    assert result == {"error": "Failed to get repository content"}
