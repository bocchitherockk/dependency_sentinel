import asyncio

from common.schemas.Dependency import Dependency
from common.schemas.File import File
from common.schemas.ManifestFile import ManifestFile
from common.schemas.Registry import Registry
from llm_service.llm_clients.llm_client import LLMClient


class DummyLLMClient(LLMClient):
    def __init__(self, chat_result):
        self.chat_result = chat_result
        self.chat_calls = []

    async def chat(self, system_instructions, prompt, response_format=None, **kwargs):
        self.chat_calls.append(
            {
                "system_instructions": system_instructions,
                "prompt": prompt,
                "response_format": response_format,
                "kwargs": kwargs,
            }
        )
        return self.chat_result


def test_detect_manifests_returns_matching_files():
    files = [
        File(path="/repo/package.json", name="package.json"),
        File(path="/repo/pom.xml", name="pom.xml"),
    ]
    client = DummyLLMClient(["/repo/pom.xml", "/repo/missing.json"])

    result = asyncio.run(client.detect_manifests(files))

    assert result == [files[1]]
    assert len(client.chat_calls) == 1
    assert "package.json" in client.chat_calls[0]["prompt"]
    assert client.chat_calls[0]["response_format"] == client.detect_manifests_response_format()


def test_extract_dependencies_builds_manifest_file():
    client = DummyLLMClient(
        {
            "path": "/repo/package.json",
            "dependencies": [
                {
                    "name": "axios",
                    "version": "^1.0.0",
                    "registry": {"name": "npm", "url": "https://registry.npmjs.org/"},
                }
            ],
            "dev_dependencies": [],
        }
    )
    manifest_file = File(
        path="/repo/package.json",
        name="package.json",
        content='{"name": "demo"}',
    )

    result = asyncio.run(client.extract_dependencies(manifest_file))

    assert result == ManifestFile(
        path="/repo/package.json",
        dependencies=[
            Dependency(
                name="axios",
                version="^1.0.0",
                registry=Registry(name="npm", url="https://registry.npmjs.org/"),
            )
        ],
        dev_dependencies=[],
    )
    assert len(client.chat_calls) == 1
    assert "package.json" in client.chat_calls[0]["prompt"]
    assert client.chat_calls[0]["response_format"] == client.extract_dependencies_response_format()


def test_prompt_manifest_files_detection_lists_paths():
    client = DummyLLMClient([])
    files = [
        File(path="/repo/package.json", name="package.json"),
        File(path="/repo/pom.xml", name="pom.xml"),
    ]

    prompt = client.prompt_manifest_files_detection(files)

    assert "/repo/package.json" in prompt
    assert "/repo/pom.xml" in prompt


def test_prompt_extract_dependencies_includes_content():
    client = DummyLLMClient([])
    manifest_file = File(path="/repo/package.json", name="package.json", content='{"name": "demo"}')

    prompt = client.prompt_extract_dependencies(manifest_file)

    assert "/repo/package.json" in prompt
    assert '{"name": "demo"}' in prompt