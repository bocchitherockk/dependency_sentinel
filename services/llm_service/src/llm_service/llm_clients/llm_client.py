from abc import ABC, abstractmethod
from typing import Any

class LLMClient(ABC):
    @abstractmethod
    async def chat(
        self,
        system_instructions: str,
        prompt: str,
        response_format: str | dict[str, any]=None,
        **kwargs,
    ):
        pass

    async def detect_manifests(self, files: list[str]):
        return await self.chat(
            system_instructions=self.system_instructions_manifest_files_detection(),
            prompt=self.prompt_manifest_files_detection(files),
            response_format=self.detect_manifests_response_format(),
        )

    async def extract_dependencies(self, manifest_file: dict[str, Any]):
        return await self.chat(
            system_instructions=self.system_instructions_extract_dependencies(),
            prompt=self.prompt_extract_dependencies(manifest_file),
            response_format=self.extract_dependencies_response_format(),
        )

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


For every detected manifest:
- identify the programming language
- identify the dependency manager
- explain briefly why it is a manifest

Only return valid JSON matching the provided schema.
"""

    def prompt_manifest_files_detection(self, files: list[str], **kwargs) -> str:
        return f"""
Here is the list of files in the project:
```
{"\n".join(files)}
```
"""

    def system_instructions_extract_dependencies(self, **kwargs) -> str:
        return """
You are an expert software engineer.

Your task is to extract each dependency and its version from a dependency manifest file.
Extract also the dev dependencies if they are present.
Return only the extracted dependencies in JSON format.
Do not change the path of the files.
Put the dependency version as they are.

Example:
{
    "manifest_file": {
        "path": "full/path/to/file/dont/change/it",
        "dependencies": [
            {
                "name": "axios",
                "version": "^1.14.0"
            }
        ],
        "dev_dependencies": [
            {
                "name": "jest",
                "version": "^29.0.0"
            }
        ]
    }
}
"""

    def prompt_extract_dependencies(self, manifest_file: dict[str, Any], **kwargs) -> str:
        return f"""
Here is the file path: `{manifest_file['path']}`,
and here is its content:
```
{manifest_file['content']}
```
"""

    def detect_manifests_response_format(self, **kwargs) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "manifest_files": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "path":                 { "type": "string" },
                            "programming_language": { "type": "string" },
                            "dependency_manager":   { "type": ["string", "null"] },
                            "reasoning":            { "type": "string" }, # A brief explanation of why the file is considered a manifest. Note: This field is just for debugging purposes and will not be used in deployment.
                        },
                        "required": [
                            "path",
                            "programming_language",
                            "dependency_manager",
                            "reasoning",
                        ],
                        "additionalProperties": False,
                    },
                },
            },
            "required": [
                "manifest_files",
            ],
            "additionalProperties": False,
        }

    def extract_dependencies_response_format(self, **kwargs) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                'manifest_file': {
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
                                },
                                "required": [
                                    "name",
                                    "version",
                                ],
                                "additionalProperties": False,
                            },
                        },
                        "dev-dependencies": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "name":    { "type": "string" },
                                    "version": { "type": ["string", "null"] },
                                },
                                "required": [
                                    "name",
                                    "version",
                                ],
                                "additionalProperties": False,
                            },
                        },
                    },
                    "required": [
                        "path",
                        "dependencies",
                        "dev-dependencies",
                    ],
                    "additionalProperties": False,
                }
            },
            "required": [
                "manifest_file",
            ],
            "additionalProperties": False,
        }
