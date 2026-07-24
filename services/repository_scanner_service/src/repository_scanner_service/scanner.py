from typing import Any

from repository_scanner_service.ollama_client import (
    detect_manifest_files,
)
from repository_scanner_service.parsers import parse_manifest
from repository_scanner_service.storage_client import (
    get_repository_content,
)


def normalize_path(path: str) -> str:
    """
    Normalize Windows and Unix paths to the same format.
    """
    return path.replace("\\", "/").strip("/")


def join_path(parent: str, child: str) -> str:
    """
    Join two repository path components.
    """
    parent = normalize_path(parent)
    child = normalize_path(child)

    if not parent:
        return child

    if not child:
        return parent

    return f"{parent}/{child}"


def find_repository_files(
    node: Any,
    current_path: str = "",
) -> list[str]:
    """
    Traverse the repository tree returned by the Storage Service
    and return every file path.

    Ollama will later decide which files are dependency manifests.
    """
    file_paths: list[str] = []

    if isinstance(node, list):
        for item in node:
            file_paths.extend(
                find_repository_files(
                    item,
                    current_path,
                )
            )

        return sorted(set(file_paths))

    if not isinstance(node, dict):
        return file_paths

    node_name = node.get("name")
    node_type = str(
        node.get("type", "")
    ).lower()

    if not isinstance(node_name, str):
        node_name = ""

    # Standard directory structure returned by the Storage Service.
    if node_type in {
        "directory",
        "folder",
        "dir",
    }:
        directory_path = join_path(
            current_path,
            node_name,
        )

        children = node.get("children", [])

        if isinstance(children, list):
            for child in children:
                file_paths.extend(
                    find_repository_files(
                        child,
                        directory_path,
                    )
                )

        return sorted(set(file_paths))

    # Standard file structure returned by the Storage Service.
    if node_type == "file":
        file_path = join_path(
            current_path,
            node_name,
        )

        if file_path:
            file_paths.append(file_path)

        return file_paths

    # Fallback when the Storage Service returns a path field.
    node_path = (
        node.get("path")
        or node.get("relative_path")
    )

    if isinstance(node_path, str):
        normalized_node_path = normalize_path(
            node_path
        )

        if normalized_node_path:
            file_paths.append(
                normalized_node_path
            )

    # Generic fallback for other possible tree structures.
    for key, value in node.items():
        if key in {
            "name",
            "type",
            "path",
            "relative_path",
            "size",
            "extension",
            "content",
            "file_content",
            "text",
        }:
            continue

        if not isinstance(value, (dict, list)):
            continue

        if key in {
            "children",
            "items",
            "entries",
            "files",
            "contents",
        }:
            next_path = current_path
        else:
            next_path = join_path(
                current_path,
                key,
            )

        file_paths.extend(
            find_repository_files(
                value,
                next_path,
            )
        )

    return sorted(set(file_paths))


def extract_file_content(
    file_data: Any,
) -> str:
    """
    Extract the real text content from a Storage Service response.
    """
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
    """
    Remove the repository root name from a complete file path.

    Example:
        project/frontend/package.json
    becomes:
        frontend/package.json
    """
    path = normalize_path(path)
    repository_name = normalize_path(
        repository_name
    )

    prefix = f"{repository_name}/"

    if path.startswith(prefix):
        return path[len(prefix):]

    return path


async def scan_repository(
    repository_name: str,
) -> dict[str, Any]:
    """
    Scan a repository using Ollama for manifest detection
    and deterministic parsers for dependency extraction.
    """
    repository_name = normalize_path(
        repository_name
    )

    if not repository_name:
        raise ValueError(
            "Le nom du repository ne peut pas être vide."
        )

    # Step 1:
    # Retrieve the complete repository tree from Storage Service.
    repository_content = get_repository_content(
        repository_name,
        show_content=False,
    )

    if (
        isinstance(repository_content, dict)
        and repository_content.get("error")
    ):
        raise ValueError(
            repository_content["error"]
        )

    # Step 2:
    # Extract every file path from the repository tree.
    repository_files = find_repository_files(
        repository_content
    )

    repository_files = sorted(
        {
            normalize_path(path)
            for path in repository_files
            if path
        }
    )

    # Step 3:
    # Send the repository file paths to Ollama.
    manifest_detections = await detect_manifest_files(
        repository_files
    )

    # Step 4:
    # Keep the paths returned and validated by ollama_client.py.
    manifest_paths = sorted(
        {
            normalize_path(
                detection.get("path", "")
            )
            for detection in manifest_detections
            if detection.get("path")
        }
    )

    # Keep Ollama metadata for each detected file.
    detection_by_path = {
        normalize_path(
            detection["path"]
        ): detection
        for detection in manifest_detections
        if detection.get("path")
    }

    results: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []

    # Step 5:
    # Retrieve and parse every detected manifest.
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
            # Retrieve the real manifest content from Storage Service.
            file_data = get_repository_content(
                full_storage_path,
                show_content=True,
            )

            if (
                isinstance(file_data, dict)
                and file_data.get("error")
            ):
                raise ValueError(
                    file_data["error"]
                )

            file_content = extract_file_content(
                file_data
            )

            # Use the deterministic parser.
            parsed_result = parse_manifest(
                relative_path,
                file_content,
            )

            detection = detection_by_path.get(
                detected_path,
                {},
            )

            parsed_result["manifest_path"] = (
                relative_path
            )

            parsed_result["detected_ecosystem"] = (
                detection.get(
                    "ecosystem",
                    "unknown",
                )
            )

            parsed_result["detection_confidence"] = (
                detection.get(
                    "confidence",
                    0,
                )
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
        len(
            result.get(
                "dependencies",
                [],
            )
        )
        for result in results
    )

    return {
        "repository": repository_name,
        "repository_file_count": len(
            repository_files
        ),
        "detected_manifest_count": len(
            manifest_paths
        ),
        "parsed_manifest_count": len(
            results
        ),
        "dependency_count": dependency_count,
        "manifest_files": manifest_paths,
        "manifest_detections": (
            manifest_detections
        ),
        "results": results,
        "errors": errors,
    }