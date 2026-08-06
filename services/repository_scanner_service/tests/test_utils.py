import asyncio

import httpx

from repository_scanner_service.utils import (
    BATCH_SIZE,
    _flatten_repository_tree,
    _detect_manifest_files,
    _extract_dependencies,
    scan_repository,
)
from common.schemas.File import File
from common.schemas.Directory import Directory
from common.schemas.ManifestFile import ManifestFile
from common.config import services

def test_flatten_repository_tree_empty_directory():
    empty_directory: Directory = Directory(name='empty', path='/empty', children=[])
    result: list[File] = _flatten_repository_tree(empty_directory)
    expected: list[File] = []
    assert result == expected
    
def test_flatten_repository_tree_single_file():
    single_file: File = File(name='file1.txt', path='/root/file1.txt')
    result: list[File] = _flatten_repository_tree(single_file)
    expected: list[File] = [single_file]
    assert result == expected

def test_flatten_repository_tree_single_file_in_directory():
    directory_with_file: Directory = Directory(
        name='dir1',
        path='/root/dir1',
        children=[File(name='file1.txt', path='/root/dir1/file1.txt')]
    )
    result: list[File] = _flatten_repository_tree(directory_with_file)
    expected: list[File] = [File(name='file1.txt', path='/root/dir1/file1.txt')]
    assert result == expected

def test_flatten_repository_tree_nested_directories():
    root: Directory = Directory(
        name='root',
        path='/root',
        children=[
            File(name='file1.txt', path='/root/file1.txt'),
            Directory(
                name='sub_dir1',
                path='/root/sub_dir1',
                children=[
                    File(name='file2.txt', path='/root/sub_dir1/file2.txt'),
                ]
            ),
            Directory(
                name='sub_dir2',
                path='/root/sub_dir2',
                children=[
                    File(name='file3.txt', path='/root/sub_dir2/file3.txt'),
                    Directory(
                        name='sub_dir3',
                        path='/root/sub_dir2/sub_dir3',
                        children=[
                            File(name='file4.txt', path='/root/sub_dir2/sub_dir3/file4.txt'),
                        ]
                    ),
                ]
            ),
        ]
    )

    # Flatten the directory structure
    result: list[File] = _flatten_repository_tree(root)
    expected: list[File] = [
        File(name='file1.txt', path='/root/file1.txt'),
        File(name='file2.txt', path='/root/sub_dir1/file2.txt'),
        File(name='file3.txt', path='/root/sub_dir2/file3.txt'),
        File(name='file4.txt', path='/root/sub_dir2/sub_dir3/file4.txt'),
    ]
    
    assert result == expected


def test_detect_manifest_files_batches_requests(monkeypatch):
    flattened_files = [
        File(name=f'file-{index}.txt', path=f'/repo/file-{index}.txt')
        for index in range(BATCH_SIZE + 1)
    ]

    recorded_requests = []

    class FakeResponse:
        def __init__(self, payload):
            self.payload = payload
        def raise_for_status(self):
            return None
        def json(self):
            return self.payload

    class FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            self.closed = False
        async def __aenter__(self):
            return self
        async def __aexit__(self, exc_type, exc, tb):
            self.closed = True
        async def post(self, url, params, json):
            recorded_requests.append((url, params, json))
            return FakeResponse([{'path': item['path'], 'name': item['name']} for item in json])

    monkeypatch.setattr(httpx, 'AsyncClient', FakeAsyncClient)

    result = asyncio.run(_detect_manifest_files(flattened_files))

    assert len(recorded_requests) == 2
    assert recorded_requests[0][0] == f"{services['llm-service']['endpoint']}/detect-manifests"
    assert recorded_requests[0][1] == {'model_name': 'qwen3:8b'}
    assert len(recorded_requests[0][2]) == BATCH_SIZE
    assert len(recorded_requests[1][2]) == 1
    assert result == [File(name=f'file-{index}.txt', path=f'/repo/file-{index}.txt') for index in range(BATCH_SIZE + 1)]


def test_extract_dependencies_uses_one_request_per_manifest(monkeypatch):
    manifest_files = [
        File(name='package.json', path='/repo/package.json'),
        File(name='pom.xml', path='/repo/pom.xml'),
    ]

    recorded_requests = []

    class FakeResponse:
        def __init__(self, payload):
            self.payload = payload
        def raise_for_status(self):
            return None
        def json(self):
            return self.payload

    class FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            pass
        async def __aenter__(self):
            return self
        async def __aexit__(self, exc_type, exc, tb):
            return None
        async def post(self, url, params, json):
            recorded_requests.append((url, params, json))
            return FakeResponse({'path': json['path'], 'dependencies': [], 'dev_dependencies': []})

    monkeypatch.setattr(httpx, 'AsyncClient', FakeAsyncClient)

    result = asyncio.run(_extract_dependencies(manifest_files))

    assert len(recorded_requests) == 2
    assert recorded_requests[0][0] == f"{services['llm-service']['endpoint']}/extract-dependencies"
    assert recorded_requests[0][1] == {'model_name': 'qwen2.5-coder:1.5b'}
    assert result == [
        ManifestFile(path='/repo/package.json', dependencies=[], dev_dependencies=[]),
        ManifestFile(path='/repo/pom.xml', dependencies=[], dev_dependencies=[]),
    ]


def test_scan_repository_requests_repository_tree_and_dependencies(monkeypatch):
    repository_name = 'example'
    repository_tree = Directory(
        name='example',
        path='/repositories/example',
        children=[File(name='package.json', path='/repositories/example/package.json')],
    )
    detected_manifest_files = [File(name='package.json', path='/repositories/example/package.json')]
    extracted_manifest_files = [
        ManifestFile(path='/repositories/example/package.json', dependencies=[], dev_dependencies=[])
    ]

    class FakeResponse:
        def __init__(self, payload):
            self.payload = payload
        def raise_for_status(self):
            return None
        def json(self):
            return self.payload

    class FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            self.get_calls = []
        async def __aenter__(self):
            return self
        async def __aexit__(self, exc_type, exc, tb):
            return None
        async def get(self, url, params=None):
            self.get_calls.append((url, params))
            if params == {'display_files_content': True}:
                return FakeResponse({'path': '/repositories/example/package.json', 'name': 'package.json', 'content': '{"name": "example"}'})
            return FakeResponse(repository_tree.model_dump(mode='json'))

    async def fake_detect_manifest_files(flattened_repository_files):
        assert flattened_repository_files == [File(name='package.json', path='/repositories/example/package.json')]
        return detected_manifest_files

    async def fake_extract_dependencies(files):
        assert files[0].content == '{"name": "example"}'
        return extracted_manifest_files

    monkeypatch.setattr(httpx, 'AsyncClient', FakeAsyncClient)
    monkeypatch.setattr('repository_scanner_service.utils._detect_manifest_files', fake_detect_manifest_files)
    monkeypatch.setattr('repository_scanner_service.utils._extract_dependencies', fake_extract_dependencies)

    result = asyncio.run(scan_repository(repository_name))

    assert result == extracted_manifest_files
