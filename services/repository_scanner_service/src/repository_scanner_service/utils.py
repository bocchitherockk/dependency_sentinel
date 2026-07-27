import httpx
import asyncio
from typing import Any

from common.config import services

def _flatten_repository_tree(node: dict) -> list[str]:
    # the node could be
    # {
    #   "path": "path/to/my-project",
    #   "name": "my-project",
    #   "type": "directory",
    #   "children": [
    #   ]
    # }
    # or it could be
    # {
    #   "path": "path/to/somefile.txt",
    #   "name": "somefile.txt",
    #   "type": "file",
    # }
    if node['type'] == 'file':
        return [node['path']]
    elif node['type'] == 'directory':
        files = []
        for child in node['children']:
            child_files = _flatten_repository_tree(child)
            files.extend(child_files)
        return files

async def _detect_manifest_files(flattened_repository_files: list[str]) -> list[dict[str, Any]]:
    """
    Ask LLM Service to detect dependency manifest files.
    Send repository paths to the LLM Service in small batches.
    Sending hundreds of paths in one request may be unreliable.
    """
    batch_size: int = 20
    async with httpx.AsyncClient(timeout=None) as client:
        # TODO: Consider using a semaphore to limit the number of concurrent requests to the LLM Service
        # because for example 2000 files / 20 = 100 concurrent requests.
        tasks = [
            client.post(
                f'{services['llm-service']['endpoint']}/detect-manifests',
                params= {'model_name': 'qwen3:8b'},
                json=flattened_repository_files[batch_index : (batch_index + batch_size)],
            )
            for batch_index in range(0, len(flattened_repository_files), batch_size)
        ]
        responses = await asyncio.gather(*tasks)

    result: list[dict[str, Any]] = []
    for response in responses:
        response.raise_for_status()
        payload = response.json()
        result.extend(payload['manifest_files'])

    return result

async def _extract_dependencies(detected_manifest_files: list[dict[str, Any]]) -> dict[str, Any]:
    """
    Ask LLM Service to extract dependencies from a manifest file.
    """
    async with httpx.AsyncClient(timeout=None) as client:
        ################## THIS IS A QUICK HACK TO SAVE TIME OR TEST #####################
        ################## ORIGINAL #####################
        tasks = [
            client.post(
                f'{services['llm-service']['endpoint']}/extract-dependencies',
                params= {'model_name': 'qwen2.5-coder:1.5b'},
                json={
                    'path':    manifest_file['path'],
                    'content': manifest_file['content'],
                },
            )
            for manifest_file in detected_manifest_files
        ]
        responses = await asyncio.gather(*tasks)
        ################## HACK #####################
        # i = 0
        # skip_indices = []
        # results = []
        # for manifest_file in detected_manifest_files:
        #     if i in skip_indices:
        #         i += 1
        #         continue
        #     print('sending request to extract dependencies for manifest file:', manifest_file['path'])
        #     response = await client.post(
        #         f'{services['llm-service']['endpoint']}/extract-dependencies',
        #         # params= {'model_name': 'qwen2.5-coder:1.5b'},
        #         params= {'model_name': 'qwen3:8b'},
        #         json={
        #             'path':    manifest_file['path'],
        #             'content': manifest_file['content'],
        #         },
        #     )
        #     print('response received for manifest file:', manifest_file['path'])
        #     response.raise_for_status()
        #     payload = response.json()
        #     results.append(payload)
        #     # manifest_file['dependencies'] = payload['dependencies']
        # return results
        ################## END #####################

    result: list[dict[str, Any]] = []
    for response in responses:
        response.raise_for_status()
        payload = response.json()
        result.append(payload['manifest_file'])

    return result

async def scan_repository(repository_name: str):
    """
    Scan a repository.

    1. Retrieve the repository tree from the Storage Service.
    2. Extract all repository file paths.
    3. Send the paths to the LLM Service, in batches, to detect manifests.
    4. Retrieve the content of every detected manifest from the Storage Service.
    5. Send the manifest content to the LLM Service to extract dependencies.
    6. Return the complete scan result.
    """
    ################## THIS IS A QUICK HACK TO SAVE TIME OR TEST #####################
    ################## ORIGINAL #####################
    # Step 1:
    # Retrieve the complete repository tree.
    async with httpx.AsyncClient() as client:
        repository_content = await client.get(
            f"{services["repository-storage-service"]["endpoint"]}/repositories/{repository_name}"
        )
        repository_content.raise_for_status()
        repository_content = repository_content.json()

    # Step 2:
    # Extract all file paths.
    flattened_repository_files: list[str] = _flatten_repository_tree(repository_content)

    # Step 3:
    # Detect manifests dynamically through the LLM Service.
    detected_manifest_files: list[dict[str, Any]] = await _detect_manifest_files(flattened_repository_files)

    ################## HACK #####################
    # detected_manifest_files = [
    #     {
    #         "path": "Plateforme-e-commerce-SaaS-avec-abonnements/angular/package.json",
    #         "programming_language": "npm",
    #         "dependency_manager": "npm",
    #         "confidence": 1.0,
    #         "reasoning": "This is the main npm package manifest file for the Angular project."
    #     },
    #     {
    #         "path": "Plateforme-e-commerce-SaaS-avec-abonnements/notifications-service/pom.xml",
    #         "programming_language": "java",
    #         "dependency_manager": "maven",
    #         "confidence": 1.0,
    #         "reasoning": "pom.xml is the standard Maven project object model file for Java projects, containing dependency declarations and build configuration"
    #     },
    #     {
    #         "path": "Plateforme-e-commerce-SaaS-avec-abonnements/orders-service/pom.xml",
    #         "programming_language": "Java",
    #         "dependency_manager": "Maven",
    #         "confidence": 1.0,
    #         "reasoning": "pom.xml is the standard Maven project configuration file containing dependency declarations for Java projects"
    #     }
    # ]
    ################## END #####################

    # Step 4:
    # Get the content of every detected manifest from the Storage Service.
    async with httpx.AsyncClient() as client:
        tasks = [
            client.get(
                f'{services['repository-storage-service']['endpoint']}/repositories/{manifest['path']}',
                params={'display_files_content': True},
            )
            for manifest in detected_manifest_files
        ]
        responses = await asyncio.gather(*tasks)

    for manifest, response in zip(detected_manifest_files, responses):
        response.raise_for_status()
        manifest['content'] = response.json()['content']

    # Step 5:
    # Ask the LLM to extract dependencies from the manifest content.
    extracted_dependencies = await _extract_dependencies(detected_manifest_files)

    # Step 6:
    # Merge the extracted dependencies into the detected manifest files.
    for manifest, extracted in zip(detected_manifest_files, extracted_dependencies):
        manifest['dependencies'] = extracted['dependencies']

    return detected_manifest_files