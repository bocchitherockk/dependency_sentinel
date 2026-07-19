from pathlib import Path

from repository_storage_service.utils import get_fs_object_content


def test_get_fs_object_content_reads_file_with_optional_content(tmp_path):
    file_path = tmp_path / "repo" / "manifest.txt"
    file_path.parent.mkdir(parents=True)
    file_path.write_text("hello world")

    without_content = get_fs_object_content(file_path)
    with_content = get_fs_object_content(file_path, display_files_content=True)

    assert without_content == {
        "repository_name": file_path.parts[1],
        "type": "file",
        "name": file_path.name,
        "path": str(file_path),
    }
    assert with_content["content"] == "hello world"


def test_get_fs_object_content_recurses_into_directories(tmp_path):
    repository_root = tmp_path / "repo"
    nested_directory = repository_root / "subdir"
    nested_directory.mkdir(parents=True)

    root_file = repository_root / "root.txt"
    nested_file = nested_directory / "nested.txt"
    root_file.write_text("root file")
    nested_file.write_text("nested file")

    content = get_fs_object_content(repository_root, display_files_content=True)
    content_by_name = {item["name"]: item for item in content}

    assert content_by_name["root.txt"]["content"] == "root file"
    assert content_by_name["subdir"]["type"] == "directory"

    nested_content = {
        item["name"]: item for item in content_by_name["subdir"]["content"]
    }
    assert nested_content["nested.txt"]["content"] == "nested file"