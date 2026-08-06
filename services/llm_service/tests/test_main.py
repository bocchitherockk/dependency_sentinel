import asyncio
import importlib
import sys

import pytest

from common.schemas.File import File
from common.schemas.ManifestFile import ManifestFile


@pytest.fixture(scope="module")
def llm_main_module():
    sys.modules.pop("llm_service.main", None)
    return importlib.import_module("llm_service.main")


class DummyModel:
    def __init__(self):
        self.detect_manifests_calls = []
        self.extract_dependencies_calls = []

    async def detect_manifests(self, files):
        self.detect_manifests_calls.append(files)
        return [files[0]]

    async def extract_dependencies(self, manifest_file):
        self.extract_dependencies_calls.append(manifest_file)
        return ManifestFile(path=str(manifest_file.path), dependencies=[], dev_dependencies=[])


def test_detect_manifests_endpoint_uses_selected_model(llm_main_module, monkeypatch):
    dummy_model = DummyModel()

    monkeypatch.setattr(llm_main_module.LLMSelector, "get_llm_model", lambda model_name: dummy_model)

    files = [
        File(path="/repo/package.json", name="package.json"),
        File(path="/repo/pom.xml", name="pom.xml"),
    ]

    result = asyncio.run(llm_main_module.detect_manifests(files, model_name="qwen3:8b"))

    assert result == [files[0]]
    assert dummy_model.detect_manifests_calls == [files]


def test_extract_dependencies_endpoint_uses_selected_model(llm_main_module, monkeypatch):
    dummy_model = DummyModel()

    monkeypatch.setattr(llm_main_module.LLMSelector, "get_llm_model", lambda model_name: dummy_model)

    manifest_file = File(path="/repo/package.json", name="package.json", content="{\"name\": \"demo\"}")

    result = asyncio.run(llm_main_module.extract_dependencies(manifest_file, model_name=None))

    assert result == ManifestFile(path="/repo/package.json", dependencies=[], dev_dependencies=[])
    assert dummy_model.extract_dependencies_calls == [manifest_file]


def test_detect_manifests_endpoint_propagates_selector_errors(llm_main_module, monkeypatch):
    def fake_get_llm_model(model_name):
        raise ValueError("LLM model 'unknown' is not supported.")

    monkeypatch.setattr(llm_main_module.LLMSelector, "get_llm_model", fake_get_llm_model)

    with pytest.raises(ValueError, match="LLM model 'unknown' is not supported."):
        asyncio.run(
            llm_main_module.detect_manifests(
                [File(path="/repo/package.json", name="package.json")],
                model_name="unknown",
            )
        )