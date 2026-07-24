from typing import Any

from repository_scanner_service.ollama_client import (
    detect_manifest_files,
)
from repository_scanner_service.parsers import parse_manifest
from repository_scanner_service.storage_client import (
    get_repository_content,
)


# Maximum number of repository paths sent to Ollama per request.
OLLAMA_BATCH_SIZE = 20


def normalize_path(path: str) -> str:
    """
    Normalize Windows and Unix paths to the same format.

    Example:
        angular\\package.json
    becomes:
        angular/package.json
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


def remove_repository_prefix(
    path: str,
    repository_name: str,
) -> str:
    """
    Remove the repository root name from a complete path.

    Example:
        my-project/angular/package.json

    becomes:
        angular/package.json
    """
    path = normalize_path(path)
    repository_name = normalize_path(repository_name)

    prefix = f"{repository_name}/"

    if path.startswith(prefix):
        return path[len(prefix):]

    return path


def find_repository_files(
    node: Any,
    current_path: str = "",
) -> list[str]:
    """
    Traverse the repository tree returned by the Storage Service
    and return all file paths.

    This function does not decide which files are manifests.
    Ollama performs the manifest detection later.
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

    if node_type == "file":
        file_path = join_path(
            current_path,
            node_name,
        )

        if file_path:
            file_paths.append(file_path)

        return file_paths

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
    Extract the text content from a Storage Service response.
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


async def detect_manifests_in_batches(
    repository_files: list[str],
    batch_size: int = OLLAMA_BATCH_SIZE,
) -> list[dict[str, Any]]:
    """
    Send repository paths to Ollama in small batches.

    Sending hundreds of paths in one request may be unreliable
    with a small local model.
    """
    if batch_size <= 0:
        raise ValueError(
            "La taille d'un lot Ollama doit être supérieure à zéro."
        )

    detections_by_path: dict[str, dict[str, Any]] = {}

    for start_index in range(
        0,
        len(repository_files),
        batch_size,
    ):
        batch = repository_files[
            start_index:start_index + batch_size
        ]

        batch_detections = await detect_manifest_files(
            batch
        )

        for detection in batch_detections:
            if not isinstance(detection, dict):
                continue

            detected_path = detection.get("path")

            if not isinstance(detected_path, str):
                continue

            normalized_path = normalize_path(
                detected_path
            )

            if not normalized_path:
                continue

            normalized_detection = dict(detection)
            normalized_detection["path"] = normalized_path

            detections_by_path[normalized_path] = (
                normalized_detection
            )

    return [
        detections_by_path[path]
        for path in sorted(detections_by_path)
    ]


async def scan_repository(
    repository_name: str,
) -> dict[str, Any]:
    """
    Scan a repository.

    Workflow:
    1. Retrieve the repository tree from Storage Service.
    2. Extract all repository file paths.
    3. Send the paths to Ollama in batches.
    4. Validate the detected manifest paths.
    5. Retrieve the content of every detected manifest.
    6. Parse dependencies using deterministic parsers.
    7. Return the complete scan result.
    """
    repository_name = normalize_path(
        repository_name
    )

    if not repository_name:
        raise ValueError(
            "Le nom du repository ne peut pas être vide."
        )

    # Step 1:
    # Retrieve the complete repository tree.
    repository_content = get_repository_content(
        repository_name,
        show_content=False,
    )

    if (
        isinstance(repository_content, dict)
        and repository_content.get("error")
    ):
        raise ValueError(
            str(repository_content["error"])
        )

    # Step 2:
    # Extract all file paths.
    raw_repository_files = find_repository_files(
        repository_content
    )

    repository_files = sorted(
        {
            remove_repository_prefix(
                normalize_path(path),
                repository_name,
            )
            for path in raw_repository_files
            if isinstance(path, str) and path
        }
    )

    if not repository_files:
        return {
            "repository": repository_name,
            "repository_file_count": 0,
            "detected_manifest_count": 0,
            "parsed_manifest_count": 0,
            "dependency_count": 0,
            "manifest_files": [],
            "manifest_detections": [],
            "results": [],
            "errors": [
                {
                    "file": repository_name,
                    "error": (
                        "Aucun fichier n'a été trouvé "
                        "dans le repository."
                    ),
                }
            ],
        }

    # Step 3:
    # Detect manifests dynamically with Ollama.
    manifest_detections = await detect_manifests_in_batches(
        repository_files
    )

    # Step 4:
    # Keep only valid paths returned by Ollama.
    repository_file_set = set(repository_files)

    valid_manifest_detections: list[dict[str, Any]] = []

    for detection in manifest_detections:
        detected_path = normalize_path(
            str(detection.get("path", ""))
        )

        if not detected_path:
            continue

        if detected_path not in repository_file_set:
            continue

        normalized_detection = dict(detection)
        normalized_detection["path"] = detected_path

        valid_manifest_detections.append(
            normalized_detection
        )

    manifest_detections = valid_manifest_detections

    manifest_paths = sorted(
        {
            detection["path"]
            for detection in manifest_detections
        }
    )

    detection_by_path = {
        detection["path"]: detection
        for detection in manifest_detections
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
            file_data = get_repository_content(
                full_storage_path,
                show_content=True,
            )

            if (
                isinstance(file_data, dict)
                and file_data.get("error")
            ):
                raise ValueError(
                    str(file_data["error"])
                )

            file_content = extract_file_content(
                file_data
            )

            # Step 6:
            # Extract dependencies using the existing parser.
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

    # Step 7:
    # Return the complete scan result.
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