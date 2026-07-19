import importlib
import os
from types import SimpleNamespace

import pytest


@pytest.fixture(scope="module")
def storage_main_module():
    patcher = pytest.MonkeyPatch()
    patcher.setattr(os, "chdir", lambda *_args, **_kwargs: None)
    patcher.setattr(os, "makedirs", lambda *_args, **_kwargs: None)

    try:
        module = importlib.import_module("repository_storage_service.main")
    finally:
        patcher.undo()

    return module


def test_clone_repository_pulls_existing_repository(storage_main_module, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    existing_repository = tmp_path / "repositories" / "example"
    existing_repository.mkdir(parents=True)

    pull_calls = []

    class FakeOrigin:
        def pull(self):
            pull_calls.append("pulled")

    class FakeRepo:
        def __init__(self, path):
            self.path = path
            self.remotes = SimpleNamespace(origin=FakeOrigin())

        @classmethod
        def clone_from(cls, *_args, **_kwargs):
            raise AssertionError("clone_from should not be called for existing repositories")

    monkeypatch.setattr(storage_main_module, "Repo", FakeRepo)

    result = storage_main_module.clone_repository("https://github.com/acme/example.git")

    assert result == {
        "message": "Repository https://github.com/acme/example.git already exists. Pulled the latest changes."
    }
    assert pull_calls == ["pulled"]


def test_clone_repository_clones_missing_repository(storage_main_module, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    clone_calls = []

    class FakeRepo:
        def __init__(self, *_args, **_kwargs):
            raise AssertionError("Repo should not be instantiated when cloning a new repository")

        @classmethod
        def clone_from(cls, repository_url, destination):
            clone_calls.append((repository_url, destination))

    monkeypatch.setattr(storage_main_module, "Repo", FakeRepo)

    result = storage_main_module.clone_repository("https://github.com/acme/new-repo.git")

    assert result == {
        "message": "Repository https://github.com/acme/new-repo.git cloned successfully."
    }
    assert clone_calls == [
        ("https://github.com/acme/new-repo.git", "./repositories/new-repo")
    ]


def test_update_file_content_writes_the_new_content(storage_main_module, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    file_path = tmp_path / "repositories" / "package" / "manifest.txt"
    file_path.parent.mkdir(parents=True)
    file_path.write_text("old content")

    result = storage_main_module.update_file_content("package/manifest.txt", "new content")

    assert file_path.read_text() == "new content"
    assert result == {"message": "File package/manifest.txt updated successfully."}