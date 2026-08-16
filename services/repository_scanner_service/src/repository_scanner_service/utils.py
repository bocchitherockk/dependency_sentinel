import asyncio

import httpx

from common.config import services
from common.schemas.Directory import Directory
from common.schemas.File import File
from common.schemas.ManifestFile import ManifestFile


BATCH_SIZE = 20  # Number of files to send in one request to the LLM Service

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
    async with httpx.AsyncClient(timeout=None) as client:
        # TODO: Consider using a semaphore to limit the number of concurrent requests to the LLM Service
        # because for example 2000 files / 20 = 100 concurrent requests.
        tasks = [
            client.post(
                f'{services['llm-service']['endpoint']}/detect-manifests',
                params= {'model_name': 'qwen3:8b'},
                # params= {'model_name': 'qwen2.5-coder:1.5b'},
                json=[flattened_repository_file.model_dump(mode='json') for flattened_repository_file in flattened_repository_files[batch_index : (batch_index + BATCH_SIZE)]],
            )
            for batch_index in range(0, len(flattened_repository_files), BATCH_SIZE)
        ]
        responses = await asyncio.gather(*tasks)

    result: list[File] = []
    for response in responses:
        response.raise_for_status()
        payload = response.json()
        for manifest_file in payload:
            result.append(File(**manifest_file))

    return result
    ################## HACK #####################
    ################## Detect manifest files only one time and then short return #####################
    # async with httpx.AsyncClient(timeout=None) as client:
    #     response = await client.post(
    #         f'{services['llm-service']['endpoint']}/detect-manifests',
    #         params= {'model_name': 'qwen3:8b'},
    #         # params= {'model_name': 'qwen2.5-coder:1.5b'},
    #         json=[flattened_repository_file.model_dump(mode='json') for flattened_repository_file in flattened_repository_files[:BATCH_SIZE]],
    #     )
    # response.raise_for_status()
    # payload = response.json()
    # result: list[File] = []
    # for manifest_file in payload:
    #     result.append(File(**manifest_file))
    # return result
    ################## HACK #####################
    ################## Return ready result without any computation #####################
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
    ################## THIS IS A QUICK HACK TO SAVE TIME OR TEST #####################
    ################## ORIGINAL #####################
    async with httpx.AsyncClient(timeout=None) as client:
        tasks = [
            client.post(
                f'{services['llm-service']['endpoint']}/extract-dependencies',
                # params= {'model_name': 'qwen2.5-coder:1.5b'},
                params= {'model_name': 'qwen3:8b'},
                json=manifest_file.model_dump(mode='json'),
            )
            for manifest_file in detected_manifest_files
        ]
        responses = await asyncio.gather(*tasks)
    result: list[ManifestFile] = []
    for response in responses:
        response.raise_for_status()
        result.append(ManifestFile(**response.json()))
    return result
    ################## HACK #####################
    ################## Extract dependencies from only 1 manifest file and then short return #####################
    # async with httpx.AsyncClient(timeout=None) as client:
    #     manifest_file = detected_manifest_files[0]
    #     response = await client.post(
    #         f'{services['llm-service']['endpoint']}/extract-dependencies',
    #         params= {'model_name': 'qwen2.5-coder:1.5b'},
    #         json=manifest_file.model_dump(mode='json'),
    #     )
    # result: list[ManifestFile] = []
    # response.raise_for_status()
    # result.append(ManifestFile(**response.json()))
    # return result
    ################## HACK #####################
    ################## Return ready result without any computation #####################
    # from common.schemas.Dependency import Dependency
    # from common.schemas.Registry import Registry

    # npm_registry: Registry = Registry(name='npm', url='https://registry.npmjs.org/')
    # maven_registry: Registry = Registry(name='maven-central', url='https://repo1.maven.org/maven2/')
    # return [
    #     ManifestFile(
    #         path='Plateforme-e-commerce-SaaS-avec-abonnements/angular/package.json',
    #         dependencies=[
    #             Dependency(name='@angular/animations'              , version='^16.1.0' , registry=npm_registry),
    #             Dependency(name='@angular/common'                  , version='^16.1.0' , registry=npm_registry),
    #             Dependency(name='@angular/compiler'                , version='^16.1.0' , registry=npm_registry),
    #             Dependency(name='@angular/core'                    , version='^16.1.0' , registry=npm_registry),
    #             Dependency(name='@angular/forms'                   , version='^16.1.0' , registry=npm_registry),
    #             Dependency(name='@angular/platform-browser'        , version='^16.1.0' , registry=npm_registry),
    #             Dependency(name='@angular/platform-browser-dynamic', version='^16.1.0' , registry=npm_registry),
    #             Dependency(name='@angular/router'                  , version='^16.1.0' , registry=npm_registry),
    #             Dependency(name='@fortawesome/fontawesome-free'    , version='^6.4.0'  , registry=npm_registry),
    #             Dependency(name='@ng-bootstrap/ng-bootstrap'       , version='^15.1.0' , registry=npm_registry),
    #             Dependency(name='@okta/okta-angular'               , version='^6.2.0'  , registry=npm_registry),
    #             Dependency(name='@okta/okta-auth-js'               , version='^6.9.0'  , registry=npm_registry),
    #             Dependency(name='@okta/okta-signin-widget'         , version='^6.2.0'  , registry=npm_registry),
    #             Dependency(name='@popperjs/core'                   , version='^2.11.6' , registry=npm_registry),
    #             Dependency(name='bootstrap'                        , version='^5.2.0'  , registry=npm_registry),
    #             Dependency(name='rxjs'                             , version='~7.8.0'  , registry=npm_registry),
    #             Dependency(name='stripe'                           , version='^8.179.0', registry=npm_registry),
    #             Dependency(name='tslib'                            , version='^2.3.0'  , registry=npm_registry),
    #             Dependency(name='zone.js'                          , version='~0.13.0' , registry=npm_registry),
    #         ],
    #         dev_dependencies=[
    #             Dependency(name='@angular-devkit/build-angular', version='^16.1.4', registry=npm_registry),
    #             Dependency(name='@angular/cli'                 , version='~16.1.4', registry=npm_registry),
    #             Dependency(name='@angular/compiler-cli'        , version='^16.1.0', registry=npm_registry),
    #             Dependency(name='@angular/localize'            , version='^16.1.0', registry=npm_registry),
    #             Dependency(name='@types/jasmine'               , version='~4.3.0' , registry=npm_registry),
    #             Dependency(name='jasmine-core'                 , version='~4.6.0' , registry=npm_registry),
    #             Dependency(name='karma'                        , version='~6.4.0' , registry=npm_registry),
    #             Dependency(name='karma-chrome-launcher'        , version='~3.2.0' , registry=npm_registry),
    #             Dependency(name='karma-coverage'               , version='~2.2.0' , registry=npm_registry),
    #             Dependency(name='karma-jasmine'                , version='~5.1.0' , registry=npm_registry),
    #             Dependency(name='karma-jasmine-html-reporter'  , version='~2.1.0' , registry=npm_registry),
    #             Dependency(name='typescript'                   , version='~5.1.3' , registry=npm_registry),
    #         ]
    #     ),
    #     ManifestFile(
    #         path='Plateforme-e-commerce-SaaS-avec-abonnements/notifications-service/pom.xml',
    #         dependencies=[
    #             Dependency(name='jackson-databind', version='2.15.2', registry=maven_registry),
    #         ],
    #         dev_dependencies=[]
    #     ),
    #     ManifestFile(
    #         path='Plateforme-e-commerce-SaaS-avec-abonnements/orders-service/pom.xml',
    #         dependencies=[
    #             Dependency(name='springdoc-openapi-starter-webmvc-ui', version='2.0.0'  , registry=maven_registry),
    #             Dependency(name='okta-spring-boot-starter'           , version='3.0.4'  , registry=maven_registry),
    #             Dependency(name='stripe-java'                        , version='22.28.0', registry=maven_registry),
    #         ],
    #         dev_dependencies=[]
    #     )
    # ]
    ################## END #####################



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

    return manifest_files