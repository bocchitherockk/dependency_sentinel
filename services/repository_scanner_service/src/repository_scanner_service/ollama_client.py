import json
import os
from typing import Any

import httpx
from dotenv import load_dotenv


load_dotenv()


OLLAMA_URL = os.getenv(
    "OLLAMA_URL",
    "http://127.0.0.1:11434",
).rstrip("/")

OLLAMA_MODEL = os.getenv(
    "OLLAMA_MODEL",
    "qwen2.5-coder:1.5b",
)

OLLAMA_TIMEOUT_SECONDS = float(
    os.getenv(
        "OLLAMA_TIMEOUT_SECONDS",
        "180",
    )
)


class OllamaClientError(RuntimeError):
    """Raised when communication with Ollama fails."""


async def check_ollama_health() -> dict[str, Any]:
    """Check the Ollama server and configured model."""

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"{OLLAMA_URL}/api/tags"
            )
            response.raise_for_status()

    except httpx.HTTPError as exc:
        raise OllamaClientError(
            f"Cannot connect to Ollama at {OLLAMA_URL}"
        ) from exc

    data = response.json()

    installed_models = [
        model.get("name") or model.get("model")
        for model in data.get("models", [])
    ]

    return {
        "status": "available",
        "ollama_url": OLLAMA_URL,
        "configured_model": OLLAMA_MODEL,
        "model_available": OLLAMA_MODEL in installed_models,
        "installed_models": installed_models,
    }


async def detect_manifest_files(
    repository_files: list[str],
) -> list[dict[str, Any]]:
    """Detect dependency manifest files using Ollama."""

    if not repository_files:
        return []

    schema = {
        "type": "object",
        "properties": {
            "manifest_files": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                        },
                        "ecosystem": {
                            "type": "string",
                        },
                        "confidence": {
                            "type": "number",
                        },
                    },
                    "required": [
                        "path",
                        "ecosystem",
                        "confidence",
                    ],
                    "additionalProperties": False,
                },
            },
        },
        "required": [
            "manifest_files",
        ],
        "additionalProperties": False,
    }

    repository_paths = "\n".join(repository_files)

    prompt = f"""
Identify dependency manifest files from the repository paths below.

Rules:
1. Return complete file paths.
2. Return only paths from the supplied list.
3. Do not return directory names.
4. Do not return source-code files.
5. Do not return README files.
6. Do not return Dockerfile.
7. Do not invent files.

Examples:
- package.json: npm
- package-lock.json: npm
- pom.xml: maven
- build.gradle: gradle
- requirements.txt: python
- pyproject.toml: python
- Pipfile: python
- Cargo.toml: cargo
- go.mod: golang
- composer.json: composer

Repository paths:

{repository_paths}
""".strip()

    payload = {
        "model": OLLAMA_MODEL,
        "stream": False,
        "format": schema,
        "options": {
            "temperature": 0,
        },
        "messages": [
            {
                "role": "system",
                "content": (
                    "You detect dependency manifest files. "
                    "Return only valid JSON matching the schema."
                ),
            },
            {
                "role": "user",
                "content": prompt,
            },
        ],
    }

    try:
        async with httpx.AsyncClient(
            timeout=OLLAMA_TIMEOUT_SECONDS,
        ) as client:
            response = await client.post(
                f"{OLLAMA_URL}/api/chat",
                json=payload,
            )
            response.raise_for_status()

    except httpx.TimeoutException as exc:
        raise OllamaClientError(
            "The Ollama request timed out."
        ) from exc

    except httpx.HTTPError as exc:
        raise OllamaClientError(
            f"Ollama request failed: {exc}"
        ) from exc

    try:
        response_data = response.json()
        content = response_data["message"]["content"]
        parsed_content = json.loads(content)

    except (
        KeyError,
        TypeError,
        json.JSONDecodeError,
    ) as exc:
        raise OllamaClientError(
            "Ollama returned an invalid JSON response."
        ) from exc

    real_paths = {
        path.replace("\\", "/"): path
        for path in repository_files
    }

    valid_manifests: list[dict[str, Any]] = []
    added_paths: set[str] = set()

    for manifest in parsed_content.get(
        "manifest_files",
        [],
    ):
        normalized_path = str(
            manifest.get("path", "")
        ).replace("\\", "/")

        # Reject paths invented by the LLM.
        if normalized_path not in real_paths:
            continue

        if normalized_path in added_paths:
            continue

        try:
            confidence = float(
                manifest.get("confidence", 0)
            )
        except (TypeError, ValueError):
            confidence = 0.0

        valid_manifests.append(
            {
                "path": real_paths[normalized_path],
                "ecosystem": str(
                    manifest.get(
                        "ecosystem",
                        "unknown",
                    )
                ).lower(),
                "confidence": max(
                    0.0,
                    min(confidence, 1.0),
                ),
            }
        )

        added_paths.add(normalized_path)

    return valid_manifests