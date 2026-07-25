"""
Client for the LLM Service.

This module is the ONLY place in repository_scanner_service that talks
to the LLM Service.
"""

import os
from typing import Any

import httpx


LLM_SERVICE_URL = os.environ.get(
    "LLM_SERVICE_URL",
    "http://127.0.0.1:8003",
)

REQUEST_TIMEOUT_SECONDS = 60.0


class OllamaClientError(Exception):
    """
    Exception raised when communication with LLM Service fails.
    """
    pass


async def detect_manifest_files(
    file_paths: list[str],
) -> list[dict[str, Any]]:
    """
    Ask LLM Service to detect dependency manifest files.
    """

    try:
        async with httpx.AsyncClient(
            timeout=REQUEST_TIMEOUT_SECONDS
        ) as client:

            response = await client.post(
                f"{LLM_SERVICE_URL}/detect-manifests",
                json=file_paths,
            )

            response.raise_for_status()

            data = response.json()

    except httpx.HTTPError as error:
        raise OllamaClientError(
            f"LLM Service manifest detection failed: {error}"
        ) from error


    if not isinstance(data, list):
        return []

    return [
        manifest
        for manifest in data
        if isinstance(manifest, dict)
    ]



async def extract_dependencies(
    manifest_path: str,
    file_content: str,
) -> dict[str, Any]:
    """
    Ask LLM Service to extract dependencies from a manifest file.
    """

    try:
        async with httpx.AsyncClient(
            timeout=REQUEST_TIMEOUT_SECONDS
        ) as client:

            response = await client.post(
                f"{LLM_SERVICE_URL}/extract-dependencies",
                json={
                    "manifest_path": manifest_path,
                    "file_content": file_content,
                },
            )

            response.raise_for_status()

            data = response.json()

    except httpx.HTTPError as error:
        raise OllamaClientError(
            f"LLM Service dependency extraction failed: {error}"
        ) from error


    if not isinstance(data, dict):
        raise OllamaClientError(
            "Invalid response received from LLM Service."
        )

    return data



async def check_ollama_health() -> dict[str, Any]:
    """
    Verify that LLM Service is reachable.
    """

    try:
        async with httpx.AsyncClient(
            timeout=REQUEST_TIMEOUT_SECONDS
        ) as client:

            response = await client.get(
                f"{LLM_SERVICE_URL}/health"
            )

            response.raise_for_status()

            return response.json()

    except httpx.HTTPError as error:
        raise OllamaClientError(
            f"LLM Service health check failed: {error}"
        ) from error