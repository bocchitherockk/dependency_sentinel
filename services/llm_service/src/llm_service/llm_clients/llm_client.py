from abc import ABC, abstractmethod
from typing import Any
from common.schemas.File import File
from common.schemas.ManifestFile import ManifestFile

class LLMClient(ABC):
    @abstractmethod
    async def chat(
        self,
        system_instructions: str,
        prompt: str,
        response_format: str | dict[str, Any]=None,
        **kwargs,
    ):
        pass

    async def detect_manifests(self, files: list[File]) -> list[File]:
        chat_result: list[str] = await self.chat(
            system_instructions=self.system_instructions_manifest_files_detection(),
            prompt=self.prompt_manifest_files_detection(files),
            response_format=self.detect_manifests_response_format(),
        )
        result: list[File] = []
        for file_path in chat_result:
            found: bool = False
            for file in files:
                if str(file.path) == file_path:
                    result.append(file)
                    found = True
                    break
            if not found:
                # raise ValueError(f"File path '{file_path}' returned by the LLM is not in the provided list of files.")
                print(f"File path '{file_path}' returned by the LLM is not in the provided list of files.")

        return result

    async def extract_dependencies(self, manifest_file: File) -> ManifestFile:
        chat_result: dict[str, Any] = await self.chat(
            system_instructions=self.system_instructions_extract_dependencies(),
            prompt=self.prompt_extract_dependencies(manifest_file),
            response_format=self.extract_dependencies_response_format(),
        )
        return ManifestFile(**chat_result)

    # These methods are here in case a specific LLM client wants to provide its own prompts and response formats, otherwise these are the default ones that will be used.
    # They accept **kwargs so that they can be customized by specific LLM clients if needed.
    def system_instructions_manifest_files_detection(self, **kwargs) -> str:
        return """
You are an expert software engineer.
Your task is to identify dependency manifest files from a list of project file paths.
A dependency manifest is a file whose purpose is to declare the dependencies used in a project.

Examples include:
- package.json
- pom.xml
- build.gradle
- build.gradle.kts
- requirements.txt
- Pipfile
- pyproject.toml
- Cargo.toml
- composer.json
- Gemfile
- go.mod
- go.sum

Return only dependency manifest files.

Ignore every other file, including source files, dependency lock files, Dockerfiles, README files, CI configuration, shell scripts, and unrelated configuration files.
Lock files are not dependency manifests, even though they contain dependency information. Examples of lock files include:
- package-lock.json
- pnpm-lock.yaml
- yarn.lock
- Pipfile.lock
- poetry.lock
- Cargo.lock
- composer.lock
- Gemfile.lock

Only return valid JSON matching the provided schema.
"""

    def prompt_manifest_files_detection(self, files: list[File], **kwargs) -> str:
        return f"""
Here is the list of files in the project:
```
{"\n".join([str(file.path) for file in files])}
```
"""

    def system_instructions_extract_dependencies(self, **kwargs) -> str:
        # TODO: here change the ist of supporeted registries to be dynamic
        return """
You are an expert software engineer.

Your task is to extract each dependency and its version from a dependency manifest file.
Extract also the dev dependencies if they are present.
Return only the extracted dependencies in JSON format.
Do not change the path of the files.
Put the dependency version as they are.

Example:
{
    "path": "full/path/to/file/dont/change/it",
    "dependencies": [
        {
            "name": "axios",
            "version": "^1.14.0",
            "registry": {
                "name": "npm",
                "url": "https://registry.npmjs.org/"
            }
        }
    ],
    "dev_dependencies": [
        {
            "name": "jest",
            "version": "^29.0.0",
            "registry": {
                "name": "maven",
                "url": "https://repo.maven.apache.org/maven2/"
            }
        }
    ]
}

here are the supporeted registries:
- npm: https://registry.npmjs.org/
- maven: https://repo.maven.apache.org/maven2/

If the dependency registry is not in the list above, return None for the registry name and url.
"""

    def prompt_extract_dependencies(self, manifest_file: File, **kwargs) -> str:
        return f"""
Here is the file path: `{str(manifest_file.path)}`,
and here is its content:
```
{manifest_file.content}
```
"""

    def detect_manifests_response_format(self, **kwargs) -> dict[str, Any]:
        return {
            "type": "array",
            "items": {
                "type": "string",
            },
            "uniqueItems": True,
        }

    def extract_dependencies_response_format(self, **kwargs) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": { "type": "string" },
                "dependencies": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name":    { "type": "string" },
                            "version": { "type": ["string", "null"] },
                            "registry": {
                                "type": "object",
                                "properties": {
                                    "name": { "type": "string" },
                                    "url":  { "type": "string" },
                                },
                                "required": [
                                    "name",
                                    "url",
                                ],
                                "additionalProperties": False,
                            },
                        },
                        "required": [
                            "name",
                            "version",
                            "registry",
                        ],
                        "additionalProperties": False,
                    },
                },
                "dev_dependencies": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name":    { "type": "string" },
                            "version": { "type": ["string", "null"] },
                            "registry": {
                                "type": "object",
                                "properties": {
                                    "name": { "type": "string" },
                                    "url":  { "type": "string" },
                                },
                                "required": [
                                    "name",
                                    "url",
                                ],
                                "additionalProperties": False,
                            },
                        },
                        "required": [
                            "name",
                            "version",
                            "registry",
                        ],
                        "additionalProperties": False,
                    },
                },
            },
            "required": [
                "path",
                "dependencies",
                "dev_dependencies",
            ],
            "additionalProperties": False,
        }
