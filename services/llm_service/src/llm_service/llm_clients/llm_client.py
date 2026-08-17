from abc import ABC, abstractmethod
from typing import Any

import fastmcp
from pydantic import TypeAdapter

from common.config import services
from common.schemas.File import File
from common.schemas.ManifestFile import ManifestFile
from common.schemas.DependencyUpdateContext import DependencyUpdateContext
from common.schemas.DependencyUpdatePlan import DependencyUpdatePlan
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
            response_format=TypeAdapter(set[str]).json_schema(),
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
                raise ValueError(f"File path '{file_path}' returned by the LLM is not in the provided list of files.")
                # print(f"File path '{file_path}' returned by the LLM is not in the provided list of files.")

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
            response_format=ManifestFile.model_json_schema(),
        )
        return ManifestFile(**chat_result)

    async def get_update_plan(self, dependency_update_context: DependencyUpdateContext) -> DependencyUpdatePlan:
        messages: list[dict[str, Any]] = [
            {
                'role': 'system',
                'content': self.system_instructions_get_update_plan()
            },
            {
                'role': 'user',
                'content': self.prompt_get_update_plan(dependency_update_context)
            }
        ]
        chat_result: dict[str, Any] = await self.chat(
            messages=messages,
            response_format=DependencyUpdatePlan.model_json_schema(),
        )
        return DependencyUpdatePlan(**chat_result)

    async def update_manifest(
        self,
        manifest_file: File,
        update_plan: ManifestFileUpdatePlan,
    ) -> str:
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
        
        async with fastmcp.Client(f"{services['mcp-server']['endpoint']}/mcp") as mcp_client:
            chat_result: str = await self.chat(
                messages=messages,
                mcp_client=mcp_client,
            )
            
        return chat_result

    # These methods are here in case a specific LLM client wants to provide its own prompts and response formats, otherwise these are the default ones that will be used.
    # They accept **kwargs so that they can be customized by specific LLM clients if needed.
    def system_instructions_manifest_files_detection(self, **kwargs) -> str:
        return '''
You are an expert software engineer.

Given a list of project file paths, identify every dependency manifest file.

A dependency manifest is a file that is conventionally used by its ecosystem to declare, configure, or manage a project's direct package dependencies.

Classify files using only their file path and file name. Do not infer file contents.

Common examples of manifest files are listed below, but the list is not exhaustive.
If you recognize another conventional dependency manifest from any programming language, package manager, or build system, include it in the result.

package.json
pom.xml
build.gradle
build.gradle.kts
requirements.txt
Pipfile
pyproject.toml
Cargo.toml
composer.json
Gemfile
go.mod
*.csproj
Directory.Packages.props
Package.swift
Podfile
mix.exs
pubspec.yaml

Return every dependency manifest you detect. A project may contain multiple manifest files.

Never return dependency lock files. Lock files record resolved dependencies but are not dependency manifests.

Examples of lock files:

package-lock.json
pnpm-lock.yaml
yarn.lock
Pipfile.lock
poetry.lock
Cargo.lock
composer.lock
Gemfile.lock

Ignore all other files, including source files, Dockerfiles, README files, CI/CD configuration, shell scripts, IDE files, and unrelated configuration files.

Return only valid JSON matching the provided schema.
'''

    def prompt_manifest_files_detection(self, files: list[File], **kwargs) -> str:
        file_list: str = '\n'.join(str(file.path) for file in files)
        return f'''
The following is the complete list of project file paths.
Each line is a relative file path.
Classify files using only these paths. Do not infer file contents.
```text
{file_list}
```
'''

    def system_instructions_extract_dependencies(self, **kwargs) -> str:
        # TODO: change the list of supporeted registries, there are not the only ones
        # the list could be contructed dynamically
        return '''
You are an expert software engineer.

Your task is to extract the direct dependencies declared in a dependency manifest file.

Return only the extracted dependencies in valid JSON matching the provided schema.

Rules:

1. Dependencies
- Extract all direct dependencies declared in the manifest.
- Extract development dependencies separately when the ecosystem distinguishes them.
- Do not include transitive dependencies.
- Do not invent dependencies.

2. Dependency name
- The `name` field must contain the dependency's canonical identifier for its ecosystem.
- Preserve the dependency name exactly as it is declared, unless the ecosystem requires combining multiple fields to form its canonical identifier.
- For ecosystems where a dependency is identified by multiple fields, combine them using the ecosystem's conventional format.

Examples:
- npm: `react`
- npm scoped package: `@types/node`
- Maven: `com.fasterxml.jackson.core:jackson-databind`
- Gradle/Maven coordinates: `org.springframework:spring-core`
- PyPI: `requests`
- Cargo: `serde`
- Go: `github.com/gin-gonic/gin`
- NuGet: `Newtonsoft.Json`

3. Dependency version
- Preserve the version string exactly as written in the manifest.
- Only include dependencies whose version is explicitly specified as a literal value in the manifest.
- If a dependency has no version, do not include it.
- If a dependency's version is represented by a variable, property, placeholder, alias, workspace reference, inherited value, or any other reference, do not include that dependency.
- Do not resolve variables or references.

This task is syntactic, not semantic.
Extract only information that is explicitly present in the provided file.
Do not use your knowledge of dependency management, or package versions
Your answer will be evaluated by comparing it directly against the contents of the provided manifest file.
Including information that is not explicitly present in the file is considered incorrect.

A dependency MUST be omitted from the output unless its version is present as a literal value in the dependency declaration itself.
An empty version string is invalid.
If the version cannot be copied directly from the dependency declaration, do not include the dependency.

For example, do not include dependencies with versions such as:
- `${spring.version}`
- `$junitVersion`
- `libs.versions.junit`
- `workspace:*`
- `workspace = true`
- `${project.version}`

Do not infer or resolve versions using:
- other files
- parent manifests
- lock files
- BOMs
- dependency management sections in other files
- imported build scripts
- version catalogs
- environment variables
- external sources

4. Registry
- Determine the registry from the dependency declaration whenever it can be determined with confidence.
- A dependency can come from a different source or registry even when it is declared in a standard manifest for an ecosystem.
- Do not assume that every dependency in a manifest uses the same registry.
- Supported registries are:
  - npm
  - maven
- If the dependency's registry cannot be determined with confidence, set `registry_name` to `null`.
- Never invent a registry name.

Examples:
- An npm package declared as `"axios": "^1.14.0"` has registry `npm`.
- An npm dependency declared using a GitHub repository is not an npm registry dependency.
- A Maven dependency using standard Maven coordinates has registry `maven`.

5. Development dependencies
- If the ecosystem distinguishes development dependencies, extract them into `dev_dependencies`.
- If the ecosystem does not distinguish development dependencies, return an empty `dev_dependencies` array.
- Apply the same version and registry rules to development dependencies.

6. File path
- Preserve the manifest file path exactly as provided.
- Do not modify, normalize, or reconstruct the path.

7. Output
- Return only valid JSON matching the provided schema.
- Do not include explanations, comments, markdown, or additional fields.

'''

    def prompt_extract_dependencies(self, manifest_file: File, **kwargs) -> str:
        return f'''
Here is the file path: `{str(manifest_file.path)}`,
and here is its content:
```text
{manifest_file.content}
```
'''

    def system_instructions_get_update_plan(self, **kwargs) -> str:
        return '''
You are a senior software engineer and cybersecurity expert.

Your task is to analyze a single DependencyUpdateContext and recommend exactly one version for the dependency.

Three candidate versions are provided:

1. current_version_dependency_report
   The version currently used by the project.

2. latest_compatible_version_dependency_report
   The newest semver-compatible version.

3. latest_version_dependency_report
   The newest available version, which may introduce breaking changes.

Each report contains the dependency version and its known security vulnerabilities.

Your objective is to recommend the version that provides the best balance between security and stability.

Decision rules:

1. Current version
- Recommend the current version if it has no known vulnerabilities.
- Also recommend the current version if upgrading does not provide a meaningful security benefit.

2. Latest compatible version
- Prefer the latest compatible version when it resolves known vulnerabilities while avoiding a potentially breaking major-version upgrade.
- Do not recommend it solely because it is newer.

3. Latest version
- Recommend the latest version only when it provides a meaningful security improvement that cannot be achieved with the latest compatible version.
- Consider that upgrading to the latest version may introduce breaking changes.

4. Security evaluation
- Compare the vulnerabilities reported for the three candidate versions.
- Prefer versions with fewer and/or less severe vulnerabilities.
- Pay particular attention to CRITICAL and HIGH severity vulnerabilities.
- Do not assume that a newer version is more secure. Base your decision only on the provided vulnerability reports.
- Do not invent vulnerabilities or other security information.

5. Reasoning
Provide a concise explanation describing:
- why the recommended version was chosen,
- why the other candidates were not selected,
- and, if recommending the latest version, mention the potential breaking-change risk.

Output rules:
- Always recommend exactly one of the three candidate versions.
- The recommended version may be the current version.
- Return only valid JSON matching the provided schema.
'''

    def prompt_get_update_plan(self, dependency_update_context: DependencyUpdateContext, **kwargs) -> str:
        dependency_update_context_json: str = dependency_update_context.model_dump_json(exclude={
            'current_version_dependency_report': {
                'vulnerabilities': {
                    'details': True,
                    'aliases': True,
                }
            },
            'latest_compatible_version_dependency_report': {
                'vulnerabilities': {
                    'details': True,
                    'aliases': True,
                }
            },
            'latest_version_dependency_report': {
                'vulnerabilities': {
                    'details': True,
                    'aliases': True,
                }
            },
        })
        return f'''
Analyze the following DependencyUpdateContext.

Determine which version should be recommended.

Do not make assumptions about vulnerabilities or versions that are not present in the provided context.

```json
{dependency_update_context_json}
```
'''

    def system_instructions_update_manifest(self, **kwargs) -> str:
        return '''
You are an expert software engineer and DevSecOps specialist.

Your task is to update a dependency manifest file according to a provided dependency update plan.

Your primary objective is to apply the requested dependency version updates by using the available MCP tools.

Tool usage:

You must use an available MCP tool to modify the manifest file.
Do not generate the updated manifest yourself unless no suitable tool exists.
If you do not use the available tool, your response is incorrect.

Editing rules:

1. Apply every requested update.
- Update each dependency to its recommended version.
- Do not update any dependency that is not present in the update plan.

2. Preserve the file.
- Preserve the original structure.
- Preserve formatting.
- Preserve indentation.
- Preserve whitespace whenever possible.
- Preserve comments.
- Preserve ordering.
- Preserve all unrelated fields.
- Do not reformat or rewrite the file.

3. Version updates.
- The only permitted modification is replacing the version of a dependency specified in the update plan with its recommended version.
- Do not rename dependencies.
- Do not add dependencies.
- Do not remove dependencies.
- Do not modify dependency scopes.
- Do not modify repositories, plugins, build configuration, or any unrelated content.

4. Variables and references.
- Do not introduce variables or property references.
- Do not resolve existing variables.
- Update only literal version values.
'''

    def prompt_update_manifest(self, manifest_file: File, update_plan: ManifestFileUpdatePlan, **kwargs) -> str:
        return f'''
Update the following dependency manifest according to the provided update plan.

Manifest file path: {manifest_file.path}

Manifest file content:
```text
{manifest_file.content}
```

Update plan:
```json
{update_plan.model_dump_json(indent=2)}
```
'''
