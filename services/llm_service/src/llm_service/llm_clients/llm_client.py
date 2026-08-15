from abc import ABC, abstractmethod
from typing import Any

import fastmcp

from common.schemas.File import File
from common.schemas.ManifestFile import ManifestFile
from common.schemas.ManifestFileUpdateContext import ManifestFileUpdateContext
from common.schemas.ManifestFileUpdatePlan import ManifestFileUpdatePlan

class LLMClient(ABC):
    @abstractmethod
    async def chat(
        self,
        messages: list[dict[str, Any]],
        response_format: None | dict[str, Any] = None,
        temperature: float = 0.0,
        think: bool = False,
        mcp_client: fastmcp.Client | None = None,
    ):
        pass

    async def detect_manifests(self, files: list[File]) -> list[File]:
        messages: list[dict[str, Any]] = [
            {
                'role': 'system',
                'content': self.system_instructions_manifest_files_detection()
            },
            {
                'role': 'user',
                'content': self.prompt_manifest_files_detection(files)
            }
        ]
        chat_result: list[str] = await self.chat(
            messages=messages,
            response_format=self.detect_manifests_response_format(),
        )
        result: list[File] = []
        for file_path in chat_result:
            found: bool = False
            for file in files:
                if str(file.path) == file_path or file.path.as_posix() == file_path:
                    result.append(file)
                    found = True
                    break
            if not found:
                # raise ValueError(f"File path '{file_path}' returned by the LLM is not in the provided list of files.")
                print(f"File path '{file_path}' returned by the LLM is not in the provided list of files.")

        return result

    async def extract_dependencies(self, manifest_file: File) -> ManifestFile:
        messages: list[dict[str, Any]] = [
            {
                'role': 'system',
                'content': self.system_instructions_extract_dependencies()
            },
            {
                'role': 'user',
                'content': self.prompt_extract_dependencies(manifest_file)
            }
        ]
        chat_result: dict[str, Any] = await self.chat(
            messages=messages,
            response_format=self.extract_dependencies_response_format(),
        )
        return ManifestFile(**chat_result)

    async def get_update_plan(self, update_context: ManifestFileUpdateContext) -> ManifestFileUpdatePlan:
        messages: list[dict[str, Any]] = [
            {
                'role': 'system',
                'content': self.system_instructions_get_update_plan()
            },
            {
                'role': 'user',
                'content': self.prompt_get_update_plan(update_context)
            }
        ]
        chat_result: dict[str, Any] = await self.chat(
            messages=messages,
            response_format=self.get_update_plan_response_format(),
        )
        return ManifestFileUpdatePlan(**chat_result)

    async def update_manifest(
        self,
        manifest_file: File,
        update_plan: ManifestFileUpdatePlan,
        mcp_client: fastmcp.Client | None = None,
    ) -> File:
        messages: list[dict[str, Any]] = [
            {
                'role': 'system',
                'content': self.system_instructions_update_manifest()
            },
            {
                'role': 'user',
                'content': self.prompt_update_manifest(manifest_file, update_plan)
            }
        ]
        
        if mcp_client is None:
            try:
                from common.config import services
                mcp_endpoint = f"{services['mcp-server']['endpoint']}/mcp"
                async with fastmcp.Client(mcp_endpoint) as client:
                    chat_result = await self.chat(
                        messages=messages,
                        mcp_client=client,
                    )
            except Exception as e:
                print(f"Notice: MCP Client connection failed or unneeded: {e}. Falling back to standard chat.")
                chat_result = await self.chat(
                    messages=messages,
                    mcp_client=None,
                )
        else:
            chat_result = await self.chat(
                messages=messages,
                mcp_client=mcp_client,
            )

        return File(
            path=manifest_file.path,
            name=manifest_file.name,
            content=chat_result if isinstance(chat_result, str) else str(chat_result)
        )


    async def analyze_security_delta(self, update_context: ManifestFileUpdateContext | dict[str, Any]) -> dict[str, Any]:
        if hasattr(update_context, "model_dump"):
            context_data = update_context.model_dump(mode="json")
        else:
            context_data = update_context
        messages: list[dict[str, Any]] = [
            {
                'role': 'system',
                'content': self.system_instructions_analyze_security_delta()
            },
            {
                'role': 'user',
                'content': self.prompt_analyze_security_delta(context_data)
            }
        ]
        chat_result: dict[str, Any] = await self.chat(
            messages=messages,
            response_format=self.analyze_security_delta_response_format(),
        )
        return chat_result

    def system_instructions_analyze_security_delta(self, **kwargs) -> str:
        return """
You are a senior cybersecurity engineer and software architect.
Your task is to analyze dependency update contexts and vulnerability deltas (comparing current version vs candidate version).
You must evaluate the security impact, determine a recommendation ('FAVORABLE', 'CAUTIOUS', or 'DISCOURAGED'), calculate a risk score (1-10), and write a clear, detailed rationale in Markdown explaining why the developer should or should not upgrade.
"""

    def prompt_analyze_security_delta(self, context_data: dict[str, Any], **kwargs) -> str:
        import json
        return f"""
Analyze the following dependency update context and vulnerability reports:

{json.dumps(context_data, indent=2)}

Determine:
1. recommendation: "FAVORABLE" if upgrading resolves CVEs without breaking changes, "CAUTIOUS" if breaking risk exists, "DISCOURAGED" if candidate introduces new vulnerabilities.
2. risk_score: Integer from 1 to 10 (1 = lowest risk, 10 = critical risk).
3. rationale: Markdown formatted explanation describing the vulnerability delta, resolved CVEs, and recommended action for the developer.
"""

    def analyze_security_delta_response_format(self, **kwargs) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "recommendation": { "type": "string", "enum": ["FAVORABLE", "CAUTIOUS", "DISCOURAGED"] },
                "risk_score": { "type": "integer" },
                "rationale": { "type": "string" }
            },
            "required": ["recommendation", "risk_score", "rationale"],
            "additionalProperties": False
        }

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

    def system_instructions_update_manifest(self, **kwargs) -> str:
        return """
You are an expert software engineer and DevSecOps specialist.
Your task is to update a project's dependency manifest file (such as package.json, pom.xml, pyproject.toml, build.gradle, etc.) based on a provided update context (UpdatePlan).
You must update the specified dependencies to their recommended secure and compatible versions while preserving the original structure, formatting, indentations, and non-dependency fields of the file.

If the tool `modify_file` is available, call `modify_file(file_path, new_content)` with the updated content to automatically persist the file changes.
Return ONLY the raw updated manifest file content. Do not wrap it in markdown code block syntax (like ```) and do not include any introductory or concluding text or commentary.
"""

    def prompt_update_manifest(self, manifest_file: File, update_context: ManifestFileUpdateContext, **kwargs) -> str:
        import json
        if hasattr(update_context, "model_dump_json"):
            context_json = update_context.model_dump_json(indent=2)
        else:
            context_json = json.dumps(update_context, indent=2)

        return f"""
Here is the original manifest file path: `{manifest_file.path}`
Here is the original manifest file content:
```
{manifest_file.content}
```

Here is the update plan context (UpdatePlan) specifying the target dependency versions and security information:
```json
{context_json}
```

Please produce the complete updated manifest file content with the target dependency versions applied.
"""

    def system_instructions_get_update_plan(self, **kwargs) -> str:
        return """
You are a senior software engineer and cybersecurity expert.
Your task is to analyze a ManifestFileUpdateContext containing dependency update contexts.
Each dependency has 3 versions with their security vulnerability reports:
1. current_version_dependency_report (the version currently in use)
2. latest_compatible_version_dependency_report (the latest semver-compatible version)
3. latest_version_dependency_report (the newest version available)

For each dependency, you must DECIDE which version to recommend:
- PREFER latest_compatible_version if it resolves known vulnerabilities without breaking backward compatibility.
- Upgrade to latest_version ONLY if latest_compatible_version still has critical vulnerabilities and latest_version is secure.
- KEEP current_version if no vulnerabilities exist or if upgrading introduces more risk.
- DO NOT blindly upgrade to latest_version. Major version changes may introduce breaking changes.

For each dependency, provide a clear reasoning explaining WHY you chose that version over the others.

If NO dependency needs an update, return empty lists.

Return only valid JSON matching the provided schema.
"""

    def prompt_get_update_plan(self, update_context: ManifestFileUpdateContext, **kwargs) -> str:
        import json
        if hasattr(update_context, "model_dump_json"):
            context_json = update_context.model_dump_json(indent=2)
        else:
            context_json = json.dumps(update_context, indent=2)

        return f"""
Analyze the following ManifestFileUpdateContext and decide which version to recommend for each dependency:

```json
{context_json}
```

For each dependency, return the name, current_version, recommended_version, and reasoning.
If a dependency does not need any update, do not include it in the result.
"""

    def get_update_plan_response_format(self, **kwargs) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "dependency_updates": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name":                { "type": "string" },
                            "current_version":     { "type": ["string", "null"] },
                            "recommended_version": { "type": ["string", "null"] },
                            "reasoning":           { "type": "string" },
                        },
                        "required": ["name", "current_version", "recommended_version", "reasoning"],
                        "additionalProperties": False,
                    },
                },
                "dev_dependency_updates": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name":                { "type": "string" },
                            "current_version":     { "type": ["string", "null"] },
                            "recommended_version": { "type": ["string", "null"] },
                            "reasoning":           { "type": "string" },
                        },
                        "required": ["name", "current_version", "recommended_version", "reasoning"],
                        "additionalProperties": False,
                    },
                },
            },
            "required": ["dependency_updates", "dev_dependency_updates"],
            "additionalProperties": False,
        }


