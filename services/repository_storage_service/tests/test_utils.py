from repository_storage_service.utils import get_fs_object_content


def test_read_file_without_content(tmp_path):
    file_path = tmp_path / "manifest.txt"
    file_path.write_text(
        "dependency==1.0.0",
        encoding="utf-8",
    )

    result = get_fs_object_content(
        file_path,
        display_files_content=False,
    )

    assert result == {
        "name": "manifest.txt",
        "type": "file",
    }


def test_read_file_with_content(tmp_path):
    file_path = tmp_path / "manifest.txt"
    file_path.write_text(
        "dependency==1.0.0",
        encoding="utf-8",
    )

    result = get_fs_object_content(
        file_path,
        display_files_content=True,
    )

    assert result == {
        "name": "manifest.txt",
        "type": "file",
        "content": "dependency==1.0.0",
    }


def test_read_directory_recursively(tmp_path):
    repository = tmp_path / "demo-repository"
    backend = repository / "backend"
    frontend = repository / "frontend"

    backend.mkdir(parents=True)
    frontend.mkdir(parents=True)

    (backend / "pom.xml").write_text(
        "<project></project>",
        encoding="utf-8",
    )

    (frontend / "package.json").write_text(
        '{"dependencies": {}}',
        encoding="utf-8",
    )

    result = get_fs_object_content(repository)

    assert result["name"] == "demo-repository"
    assert result["type"] == "directory"

    assert isinstance(result["children"], list)

    children_by_name = {
        child["name"]: child
        for child in result["children"]
    }

    assert "backend" in children_by_name
    assert "frontend" in children_by_name

    backend_result = children_by_name["backend"]

    assert backend_result["type"] == "directory"

    backend_files = {
        child["name"]
        for child in backend_result["children"]
    }

    assert "pom.xml" in backend_files

    frontend_result = children_by_name["frontend"]

    frontend_files = {
        child["name"]
        for child in frontend_result["children"]
    }

    assert "package.json" in frontend_files


def test_ignore_unnecessary_directories(tmp_path):
    repository = tmp_path / "demo-repository"
    repository.mkdir()

    ignored_directories = [
        ".git",
        ".venv",
        "node_modules",
        "target",
        "__pycache__",
        ".pytest_cache",
    ]

    for directory_name in ignored_directories:
        (repository / directory_name).mkdir()

    (repository / "src").mkdir()

    result = get_fs_object_content(repository)

    children_names = {
        child["name"]
        for child in result["children"]
    }

    assert "src" in children_names

    for directory_name in ignored_directories:
        assert directory_name not in children_names


def test_missing_path(tmp_path):
    missing_path = tmp_path / "unknown.txt"

    result = get_fs_object_content(missing_path)

    assert result == {
        "error": "File or directory not found",
    }