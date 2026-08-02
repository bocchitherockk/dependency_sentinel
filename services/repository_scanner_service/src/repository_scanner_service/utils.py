import asyncio

import httpx

from common.config import services
from common.schemas.Directory import Directory
from common.schemas.File import File
from common.schemas.ManifestFile import ManifestFile


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
    Send repository files to the LLM Service in small batches.
    Sending hundreds of files in one request may be unreliable.
    """
    ################## THIS IS A QUICK HACK TO SAVE TIME OR TEST #####################
    ################## ORIGINAL #####################
    batch_size: int = 20
    async with httpx.AsyncClient(timeout=None) as client:
        # TODO: Consider using a semaphore to limit the number of concurrent requests to the LLM Service
        # because for example 2000 files / 20 = 100 concurrent requests.
        print('sending requests ...')
        tasks = [
            client.post(
                f'{services['llm-service']['endpoint']}/detect-manifests',
                params= {'model_name': 'qwen3:8b'},
                # params= {'model_name': 'qwen2.5-coder:1.5b'},
                json=[flattened_repository_file.model_dump(mode='json') for flattened_repository_file in flattened_repository_files[batch_index : (batch_index + batch_size)]],
            )
            for batch_index in range(0, len(flattened_repository_files), batch_size)
        ]
        print('requests sent')
        print('asyncio.gather ...')
        responses = await asyncio.gather(*tasks)
        print('asyncio gathered')

    result: list[File] = []
    for response in responses:
        response.raise_for_status()
        payload = response.json()
        for manifest_file in payload:
            result.append(File(**manifest_file))

    return result
    ################## HACK #####################
    # return [
    #     File(path="Plateforme-e-commerce-SaaS-avec-abonnements/angular/package.json", name="package.json"),
    #     File(path="Plateforme-e-commerce-SaaS-avec-abonnements/notifications-service/pom.xml", name="pom.xml"),
    #     File(path="Plateforme-e-commerce-SaaS-avec-abonnements/orders-service/pom.xml", name="pom.xml"),
    # ]
    ################## END #####################

async def _extract_dependencies(detected_manifest_files: list[File]) -> list[ManifestFile]:
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
                json=manifest_file.model_dump(mode='json'),
            )
            for manifest_file in detected_manifest_files
        ]
        responses = await asyncio.gather(*tasks)
        ################## HACK #####################
        # i = 0
        # skip_indices = []
        # results: list[ManifestFile] = []
        # for manifest_file in detected_manifest_files:
        #     if i in skip_indices:
        #         i += 1
        #         continue
        #     print('sending request to extract dependencies for manifest file:', manifest_file['path'])
        #     response = await client.post(
        #         f'{services['llm-service']['endpoint']}/extract-dependencies',
        #         # params= {'model_name': 'qwen2.5-coder:1.5b'},
        #         params= {'model_name': 'qwen3:8b'},
        #         json=manifest_file.model_dump(mode='json'),
        #     )
        #     print('response received for manifest file:', manifest_file['path'])
        #     response.raise_for_status()
        #     payload = response.json()
        #     results.append(ManifestFile(**payload))
        # return results
        ################## END #####################

    result: list[ManifestFile] = []
    for response in responses:
        response.raise_for_status()
        payload = response.json()
        result.append(ManifestFile(**payload))

    return result

async def scan_repository(repository_name: str) -> list[ManifestFile]:
    """
    Scan a repository.

    1. Retrieve the repository tree from the Storage Service.
    2. Extract all repository file paths.
    3. Send the paths to the LLM Service, in batches, to detect manifests.
    4. Retrieve the content of every detected manifest from the Storage Service.
    5. Send the manifest content to the LLM Service to extract dependencies.
    6. Return the complete scan result.
    """
    # Step 1:
    # Retrieve the complete repository tree.
    async with httpx.AsyncClient() as client:
        result = await client.get(
            f"{services["repository-storage-service"]["endpoint"]}/repositories/{repository_name}"
        )
        result.raise_for_status()
        repository_content: Directory = Directory(**result.json())

    # Step 2:
    # Extract all file paths.
    flattened_repository_files: list[File] = _flatten_repository_tree(repository_content)

    # Step 3:
    # Detect manifests dynamically through the LLM Service.
    detected_manifest_files: list[File] = await _detect_manifest_files(flattened_repository_files)
    print('wawa: Detected manifest files:', detected_manifest_files)

    # Step 4:
    # Get the content of every detected manifest from the Storage Service.
    async with httpx.AsyncClient() as client:
        tasks = [
            client.get(
                f'{services['repository-storage-service']['endpoint']}/repositories/{manifest.path}',
                params={'display_files_content': True},
            )
            for manifest in detected_manifest_files
        ]
        responses = await asyncio.gather(*tasks)

    for manifest, response in zip(detected_manifest_files, responses):
        response.raise_for_status()
        payload = response.json()
        manifest.content = payload['content']
        
    # Step 5:
    # Ask the LLM to extract dependencies from the manifest content.
    manifest_files: list[ManifestFile] = await _extract_dependencies(detected_manifest_files)

    # Step 6:
    # Merge the extracted dependencies into the detected manifest files.
    # for manifest, extracted in zip(detected_manifest_files, extracted_dependencies):
    #     manifest.dependencies = extracted.dependencies

    return [manifest_file.model_dump() for manifest_file in manifest_files]