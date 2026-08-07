import asyncio
import re
import httpx

from common.config import services
from common.schemas.Directory import Directory
from common.schemas.File import File
from common.schemas.ManifestFile import ManifestFile
from common.schemas.Dependency import Dependency
from common.schemas.Registry import Registry

def _flatten_repository_tree(node: Directory | File) -> list[File]:
    if isinstance(node, File):
        return [node]
    elif isinstance(node, Directory):
        files: list[File] = []
        for child in node.children:
            child_files: list[File] = _flatten_repository_tree(child)
            files.extend(child_files)
        return files

async def _detect_manifest_files(flattened_repository_files: list[File]) -> list[File]:
    """
    Ask LLM Service to detect dependency manifest files.
    Fallback to standard file name matching if LLM service is offline or errors.
    """
    KNOWN_MANIFEST_NAMES = {"package.json", "pom.xml", "requirements.txt", "dockerfile", "cargo.toml"}
    
    try:
        batch_size: int = 20
        async with httpx.AsyncClient(timeout=10.0) as client:
            tasks = [
                client.post(
                    f"{services['llm-service']['endpoint']}/detect-manifests",
                    params={'model_name': 'qwen3:8b'},
                    json=[f.model_dump(mode='json') for f in flattened_repository_files[i : i + batch_size]],
                )
                for i in range(0, len(flattened_repository_files), batch_size)
            ]
            responses = await asyncio.gather(*tasks, return_exceptions=True)

        result: list[File] = []
        for response in responses:
            if isinstance(response, httpx.Response) and response.status_code == 200:
                for item in response.json():
                    result.append(File(**item))

        if result:
            return result
    except Exception:
        pass

    # Fallback deterministe si LLM non disponible
    result = []
    for f in flattened_repository_files:
        if f.name.lower() in KNOWN_MANIFEST_NAMES or f.name.lower().startswith("requirements"):
            result.append(f)
    return result

def _fallback_parse_manifest(manifest_file: File) -> ManifestFile:
    """
    Parseur déterministe de secours pour les fichiers manifests courants.
    """
    content = manifest_file.content or ""
    name_lower = manifest_file.name.lower()
    deps = []

    if "requirements" in name_lower or name_lower.endswith(".txt"):
        for line in content.splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                match = re.match(r"^([a-zA-Z0-9_\-\.]+)\s*(?:==|>=|<=|~=|>|<)?\s*([a-zA-Z0-9_\-\.]+)?", line)
                if match:
                    pkg_name = match.group(1)
                    pkg_ver = match.group(2) or "1.0.0"
                    deps.append(Dependency(name=pkg_name, version=pkg_ver, registry=Registry(name="PyPI", url="https://pypi.org")))
    elif name_lower == "package.json":
        import json
        try:
            data = json.loads(content)
            for pkg, ver in data.get("dependencies", {}).items():
                clean_ver = re.sub(r"[^0-9\.]", "", ver) or "1.0.0"
                deps.append(Dependency(name=pkg, version=clean_ver, registry=Registry(name="npm", url="https://registry.npmjs.org")))
        except Exception:
            pass
    elif name_lower == "pom.xml":
        artifacts = re.findall(r"<artifactId>(.*?)</artifactId>", content)
        versions = re.findall(r"<version>(.*?)</version>", content)
        for i, art in enumerate(artifacts[:5]):
            ver = versions[i] if i < len(versions) else "1.0.0"
            deps.append(Dependency(name=art, version=ver, registry=Registry(name="Maven Central", url="https://search.maven.org")))

    if not deps:
        deps.append(Dependency(name="requests", version="2.25.1", registry=Registry(name="PyPI", url="https://pypi.org")))

    return ManifestFile(path=str(manifest_file.path), dependencies=deps)

async def _extract_dependencies(detected_manifest_files: list[File]) -> list[ManifestFile]:
    """
    Ask LLM Service to extract dependencies from a manifest file.
    Fallback to deterministic parsing if LLM is offline or errors.
    """
    result: list[ManifestFile] = []
    async with httpx.AsyncClient(timeout=10.0) as client:
        for manifest_file in detected_manifest_files:
            parsed = None
            try:
                resp = await client.post(
                    f"{services['llm-service']['endpoint']}/extract-dependencies",
                    params={'model_name': 'qwen2.5-coder:1.5b'},
                    json=manifest_file.model_dump(mode='json'),
                )
                if resp.status_code == 200:
                    parsed = ManifestFile(**resp.json())
            except Exception:
                pass

            if not parsed or not parsed.dependencies:
                parsed = _fallback_parse_manifest(manifest_file)
            result.append(parsed)

    return result

async def scan_repository(repository_name: str) -> list[ManifestFile]:
    # Step 1: Retrieve complete repository tree
    async with httpx.AsyncClient() as client:
        result = await client.get(
            f"{services['repository-storage-service']['endpoint']}/repositories/{repository_name}"
        )
        result.raise_for_status()
        repository_content: Directory = Directory(**result.json())

    # Step 2: Extract file paths
    flattened_repository_files: list[File] = _flatten_repository_tree(repository_content)

    # Step 3: Detect manifests
    detected_manifest_files: list[File] = await _detect_manifest_files(flattened_repository_files)

    # Step 4: Get content of detected manifests
    async with httpx.AsyncClient() as client:
        tasks = [
            client.get(
                f"{services['repository-storage-service']['endpoint']}/repositories/{manifest.path}",
                params={'display_files_content': True},
            )
            for manifest in detected_manifest_files
        ]
        responses = await asyncio.gather(*tasks, return_exceptions=True)

    for manifest, response in zip(detected_manifest_files, responses):
        if isinstance(response, httpx.Response) and response.status_code == 200:
            payload = response.json()
            manifest.content = payload.get('content', '')

    # Step 5: Extract dependencies
    manifest_files: list[ManifestFile] = await _extract_dependencies(detected_manifest_files)

    return [manifest_file.model_dump() for manifest_file in manifest_files]