from typing import Any

from repository_scanner_service.parsers import parse_manifest
from repository_scanner_service.storage_client import get_repository_content


MANIFEST_FILES = {
    "pom.xml",
    "package.json",
    "pyproject.toml",
    "requirements.txt",
}


def normalize_path(path: str) -> str:
    return path.replace("\\", "/").strip("/")


def join_path(parent: str, child: str) -> str:
    parent = normalize_path(parent)
    child = normalize_path(child)

    if not parent:
        return child

    if not child:
        return parent

    return f"{parent}/{child}"


from typing import Any

from repository_scanner_service.parsers import parse_manifest
from repository_scanner_service.storage_client import get_repository_content


MANIFEST_FILES = {
    "pom.xml",
    "package.json",
    "pyproject.toml",
    "requirements.txt",
}


def normalize_path(path: str) -> str:
    return path.replace("\\", "/").strip("/")


def join_path(parent: str, child: str) -> str:
    parent = normalize_path(parent)
    child = normalize_path(child)

    if not parent:
        return child

    if not child:
        return parent

    return f"{parent}/{child}"


def find_manifest_files(
    node: Any,
    current_path: str = "",
) -> list[str]:
    manifest_paths: list[str] = []

    if isinstance(node, list):
        for item in node:
            manifest_paths.extend(
                find_manifest_files(item, current_path)
            )

        return manifest_paths

    if isinstance(node, str):
        normalized_value = normalize_path(node)
        file_name = normalized_value.split("/")[-1]

        if file_name in MANIFEST_FILES:
            if "/" in normalized_value:
                manifest_paths.append(normalized_value)
            else:
                manifest_paths.append(
                    join_path(current_path, normalized_value)
                )

        return manifest_paths

    if not isinstance(node, dict):
        return manifest_paths

    node_name = node.get("name")
    node_path = node.get("path") or node.get("relative_path")
    node_type = str(node.get("type", "")).lower()

    if isinstance(node_path, str):
        normalized_node_path = normalize_path(node_path)

        if normalized_node_path.split("/")[-1] in MANIFEST_FILES:
            manifest_paths.append(normalized_node_path)

    if isinstance(node_name, str):
        full_node_path = join_path(current_path, node_name)

        if node_name in MANIFEST_FILES:
            manifest_paths.append(full_node_path)

        if node_type in {"directory", "folder", "dir"}:
            next_path = full_node_path
        else:
            next_path = current_path
    else:
        next_path = current_path

    for key, value in node.items():
        if key in {
            "name",
            "type",
            "path",
            "relative_path",
            "size",
            "extension",
        }:
            continue

        key_path = join_path(next_path, key)

        if key in MANIFEST_FILES:
            manifest_paths.append(key_path)

        if isinstance(value, (dict, list)):
            manifest_paths.extend(
                find_manifest_files(
                    value,
                    key_path if key not in {
                        "children",
                        "items",
                        "entries",
                        "files",
                        "contents",
                        "content",
                    } else next_path,
                )
            )

        elif isinstance(value, str):
            normalized_value = normalize_path(value)
            value_name = normalized_value.split("/")[-1]

            if value_name in MANIFEST_FILES:
                if "/" in normalized_value:
                    manifest_paths.append(normalized_value)
                else:
                    manifest_paths.append(
                        join_path(next_path, normalized_value)
                    )

    return sorted(set(manifest_paths))


def extract_file_content(file_data: Any) -> str:
    if isinstance(file_data, str):
        return file_data

    if isinstance(file_data, dict):
        for key in (
            "content",
            "file_content",
            "text",
        ):
            value = file_data.get(key)

            if isinstance(value, str):
                return value

        if len(file_data) == 1:
            only_value = next(iter(file_data.values()))

            if isinstance(only_value, str):
                return only_value

        for value in file_data.values():
            if isinstance(value, (dict, list)):
                try:
                    return extract_file_content(value)
                except ValueError:
                    continue

    if isinstance(file_data, list):
        for value in file_data:
            try:
                return extract_file_content(value)
            except ValueError:
                continue

    raise ValueError(
        "Le contenu du fichier n'a pas été trouvé."
    )


def remove_repository_prefix(
    path: str,
    repository_name: str,
) -> str:
    path = normalize_path(path)
    repository_name = normalize_path(repository_name)

    prefix = f"{repository_name}/"

    if path.startswith(prefix):
        return path[len(prefix):]

    return path


def scan_repository(repository_name: str) -> dict[str, Any]:
    repository_name = normalize_path(repository_name)

    if not repository_name:
        raise ValueError(
            "Le nom du repository ne peut pas être vide."
        )

    repository_content = get_repository_content(
        repository_name,
        show_content=False,
    )

    manifest_paths = find_manifest_files(
        repository_content
    )

    manifest_paths = sorted(
        {
            normalize_path(path)
            for path in manifest_paths
            if path
        }
    )

    results: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []

    for detected_path in manifest_paths:
        relative_path = remove_repository_prefix(
            detected_path,
            repository_name,
        )

        full_storage_path = join_path(
            repository_name,
            relative_path,
        )

        try:
            file_data = get_repository_content(
                full_storage_path,
                show_content=True,
            )

            file_content = extract_file_content(
                file_data
            )

            parsed_result = parse_manifest(
                relative_path,
                file_content,
            )

            results.append(parsed_result)

        except Exception as error:
            errors.append(
                {
                    "file": relative_path,
                    "error": str(error),
                }
            )

    dependency_count = sum(
        len(result.get("dependencies", []))
        for result in results
    )

    return {
        "repository": repository_name,
        "detected_manifest_count": len(manifest_paths),
        "parsed_manifest_count": len(results),
        "dependency_count": dependency_count,
        "manifest_files": manifest_paths,
        "results": results,
        "errors": errors,
    }
def extract_file_content(file_data: Any) -> str:
    if isinstance(file_data, str):
        return file_data

    if isinstance(file_data, dict):
        for key in (
            "content",
            "file_content",
            "text",
        ):
            value = file_data.get(key)

            if isinstance(value, str):
                return value

        if len(file_data) == 1:
            only_value = next(iter(file_data.values()))

            if isinstance(only_value, str):
                return only_value

        for value in file_data.values():
            if isinstance(value, (dict, list)):
                try:
                    return extract_file_content(value)
                except ValueError:
                    continue

    if isinstance(file_data, list):
        for value in file_data:
            try:
                return extract_file_content(value)
            except ValueError:
                continue

    raise ValueError(
        "Le contenu du fichier n'a pas été trouvé."
    )


def remove_repository_prefix(
    path: str,
    repository_name: str,
) -> str:
    path = normalize_path(path)
    repository_name = normalize_path(repository_name)

    prefix = f"{repository_name}/"

    if path.startswith(prefix):
        return path[len(prefix):]

    return path


def scan_repository(repository_name: str) -> dict[str, Any]:
    repository_name = normalize_path(repository_name)

    if not repository_name:
        raise ValueError(
            "Le nom du repository ne peut pas être vide."
        )

    repository_content = get_repository_content(
        repository_name,
        show_content=False,
    )

    manifest_paths = find_manifest_files(
        repository_content
    )

    manifest_paths = sorted(
        {
            normalize_path(path)
            for path in manifest_paths
            if path
        }
    )

    results: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []

    for detected_path in manifest_paths:
        relative_path = remove_repository_prefix(
            detected_path,
            repository_name,
        )

        full_storage_path = join_path(
            repository_name,
            relative_path,
        )

        try:
            file_data = get_repository_content(
                full_storage_path,
                show_content=True,
            )

            file_content = extract_file_content(
                file_data
            )

            parsed_result = parse_manifest(
                relative_path,
                file_content,
            )

            results.append(parsed_result)

        except Exception as error:
            errors.append(
                {
                    "file": relative_path,
                    "error": str(error),
                }
            )

    dependency_count = sum(
        len(result.get("dependencies", []))
        for result in results
    )

    return {
        "repository": repository_name,
        "detected_manifest_count": len(manifest_paths),
        "parsed_manifest_count": len(results),
        "dependency_count": dependency_count,
        "manifest_files": manifest_paths,
        "results": results,
        "errors": errors,
    }