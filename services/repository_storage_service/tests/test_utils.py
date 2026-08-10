from pathlib import Path

from repository_storage_service.utils import get_fs_object, remove_repository_name_prefix
from common.schemas.File import File
from common.schemas.Directory import Directory

def test_read_file_without_content(tmp_path: Path):
    file_path: Path = tmp_path / 'manifest.txt'
    file_path.write_text('dependency==1.0.0', encoding='utf-8')

    result: File = get_fs_object(file_path, display_files_content=False)
    expected: File = File(path=file_path, name='manifest.txt')
    print(f"Result: {result}")
    print(f"Expected: {expected}")
    assert result == expected

def test_read_file_with_content(tmp_path: Path):
    file_path: Path = tmp_path / 'manifest.txt'
    file_path.write_text('dependency==1.0.0', encoding='utf-8')

    result: File = get_fs_object(file_path, display_files_content=True)
    expected: File = File(path=file_path, name='manifest.txt', content='dependency==1.0.0')
    assert result == expected

def test_read_nested_file_without_content(tmp_path: Path):
    subdir1:   Path = tmp_path / 'subdir1'
    subdir2:   Path = subdir1 / 'subdir2'
    file_path: Path = subdir2 / 'manifest.txt'
    subdir1.mkdir()
    subdir2.mkdir()

    file_path.write_text('dependency==1.0.0', encoding='utf-8')

    result: File = get_fs_object(file_path, display_files_content=False)
    expected: File = File(path=file_path, name='manifest.txt')
    assert result == expected

def test_read_nested_file_with_content(tmp_path: Path):
    subdir1:   Path = tmp_path / 'subdir1'
    subdir2:   Path = subdir1 / 'subdir2'
    file_path: Path = subdir2 / 'manifest.txt'
    subdir1.mkdir()
    subdir2.mkdir()
    file_path.write_text('dependency==1.0.0', encoding='utf-8')

    result: File = get_fs_object(file_path, display_files_content=True)
    expected: File = File(path=file_path, name='manifest.txt', content='dependency==1.0.0')
    assert result == expected

def test_read_directory_without_content(tmp_path: Path):
    repository: Path = tmp_path / 'demo-repository'
    backend:    Path = repository / 'backend'
    frontend:   Path = repository / 'frontend'
    tests:      Path = backend / 'tests'
    repository.mkdir()
    backend.mkdir()
    frontend.mkdir()
    tests.mkdir()

    pom_file: Path = backend / 'pom.xml'
    test_file: Path = tests / 'test_example.py'
    readme_file: Path = frontend / 'README.md'
    package_json_file: Path = frontend / 'package.json'
    
    pom_file.write_text('<project></project>', encoding='utf-8')
    test_file.write_text('def test_example():\n    pass', encoding='utf-8')
    package_json_file.write_text('{"dependencies": {}}', encoding='utf-8')
    readme_file.write_text('# Demo Repository', encoding='utf-8')

    result: Directory = get_fs_object(repository, display_files_content=False)
    expected: Directory = Directory(
        path=repository,
        name='demo-repository',
        children=[
            Directory(
                path=backend,
                name='backend',
                children=[
                    File(path=pom_file, name='pom.xml'),
                    Directory(
                        path=tests,
                        name='tests',
                        children=[
                            File(path=test_file, name='test_example.py')
                        ]
                    )
                ]
            ),
            Directory(
                path=frontend,
                name='frontend',
                children=[
                    File(path=package_json_file, name='package.json'),
                    File(path=readme_file, name='README.md'),
                ]
            )
        ]
    )
    assert result == expected
    
def test_read_directory_with_content(tmp_path: Path):
    repository: Path = tmp_path / 'demo-repository'
    backend:    Path = repository / 'backend'
    frontend:   Path = repository / 'frontend'
    tests:      Path = backend / 'tests'
    repository.mkdir()
    backend.mkdir()
    frontend.mkdir()
    tests.mkdir()

    pom_file: Path = backend / 'pom.xml'
    test_file: Path = tests / 'test_example.py'
    package_json_file: Path = frontend / 'package.json'
    readme_file: Path = frontend / 'README.md'
    
    pom_file.write_text('<project></project>', encoding='utf-8')
    test_file.write_text('def test_example():\n    pass', encoding='utf-8')
    package_json_file.write_text('{"dependencies": {}}', encoding='utf-8')
    readme_file.write_text('# Demo Repository', encoding='utf-8')

    result: Directory = get_fs_object(repository, display_files_content=True)
    expected: Directory = Directory(
        path=repository,
        name='demo-repository',
        children=[
            Directory(
                path=backend,
                name='backend',
                children=[
                    File(path=pom_file, name='pom.xml', content='<project></project>'),
                    Directory(
                        path=tests,
                        name='tests',
                        children=[
                            File(path=test_file, name='test_example.py', content='def test_example():\n    pass')
                        ]
                    )
                ]
            ),
            Directory(
                path=frontend,
                name='frontend',
                children=[
                    File(path=package_json_file, name='package.json', content='{"dependencies": {}}'),
                    File(path=readme_file, name='README.md', content='# Demo Repository'),
                ]
            )
        ]
    )
    assert result == expected


def test_ignore_unnecessary_directories(tmp_path: Path):
    repository: Path = tmp_path / 'demo-repository'
    git: Path = repository / '.git'
    venv: Path = repository / '.venv'
    node_modules: Path = repository / 'node_modules'
    target: Path = repository / 'target'
    pycache: Path = repository / '__pycache__'
    pytest_cache: Path = repository / '.pytest_cache'
    src: Path = repository / 'src'

    repository.mkdir()
    git.mkdir()
    venv.mkdir()
    node_modules.mkdir()
    target.mkdir()
    pycache.mkdir()
    pytest_cache.mkdir()
    src.mkdir()
    
    file1: Path = src / 'file1.txt'
    file2: Path = src / 'file2.txt'

    file1.write_text('Content of file 1', encoding='utf-8')
    file2.write_text('Content of file 2', encoding='utf-8')
    
    result: Directory = get_fs_object(repository, display_files_content=False)
    expected: Directory = Directory(
        path=repository,
        name='demo-repository',
        children=[
            Directory(
                path=src,
                name='src',
                children=[
                    File(path=file1, name='file1.txt'),
                    File(path=file2, name='file2.txt')
                ]
            )
        ]
    )
    
    assert result == expected

def test_missing_path(tmp_path: Path):
    missing_path: Path = tmp_path / 'unknown.txt'
    try:
        get_fs_object(missing_path)
        assert False
    except FileNotFoundError:
        assert True
        
def test_remove_repository_name_prefix(tmp_path: Path):
    repository: Path = tmp_path / 'demo-repository'
    backend:    Path = repository / 'backend'
    frontend:   Path = repository / 'frontend'
    tests:      Path = backend / 'tests'
    repository.mkdir()
    backend.mkdir()
    frontend.mkdir()
    tests.mkdir()

    pom_file: Path = backend / 'pom.xml'
    test_file: Path = tests / 'test_example.py'
    package_json_file: Path = frontend / 'package.json'
    readme_file: Path = frontend / 'README.md'
    
    pom_file.write_text('<project></project>', encoding='utf-8')
    test_file.write_text('def test_example():\n    pass', encoding='utf-8')
    package_json_file.write_text('{"dependencies": {}}', encoding='utf-8')
    readme_file.write_text('# Demo Repository', encoding='utf-8')

    result: Directory = get_fs_object(repository, display_files_content=False)
    
    result_without_prefix: Directory = remove_repository_name_prefix(result, repository)
    
    expected: Directory = Directory(
        path=Path('.'),
        name='demo-repository',
        children=[
            Directory(
                path=Path('backend'),
                name='backend',
                children=[
                    File(path=Path('backend/pom.xml'), name='pom.xml'),
                    Directory(
                        path=Path('backend/tests'),
                        name='tests',
                        children=[
                            File(path=Path('backend/tests/test_example.py'), name='test_example.py')
                        ]
                    )
                ]
            ),
            Directory(
                path=Path('frontend'),
                name='frontend',
                children=[
                    File(path=Path('frontend/package.json'), name='package.json'),
                    File(path=Path('frontend/README.md'), name='README.md'),
                ]
            )
        ]
    )
    
    assert result_without_prefix == expected