import uvicorn
from fastapi import FastAPI, HTTPException

from common.config import services
from repository_scanner_service.ollama_client import (
    OllamaClientError,
    check_ollama_health,
    detect_manifest_files,
)
from repository_scanner_service.scanner import scan_repository


app = FastAPI(
    title="Repository Scanner Service",
    description=(
        "Scans repositories, detects dependency manifest files "
        "with Ollama, and extracts their dependencies."
    ),
    version="0.2.0",
)


@app.get("/")
def home() -> dict[str, str]:
    """
    Verify that the Repository Scanner Service is running.
    """
    return {
        "service": "repository-scanner-service",
        "message": "Repository Scanner Service is running.",
    }


@app.get("/ollama/health")
async def ollama_health() -> dict:
    """
    Verify that the Scanner Service can communicate with Ollama
    and that the configured model is installed.
    """
    try:
        return await check_ollama_health()

    except OllamaClientError as error:
        raise HTTPException(
            status_code=503,
            detail=str(error),
        ) from error


@app.post("/ollama/test")
async def test_ollama_manifest_detection() -> dict:
    """
    Test Ollama manifest detection using example repository paths.

    This route is temporary and is used before integrating Ollama
    into the real repository scanning workflow.
    """
    repository_files = [
        "frontend/package.json",
        "frontend/package-lock.json",
        "backend/pom.xml",
        "backend/src/main.py",
        "python-service/requirements.txt",
        "python-service/main.py",
        "README.md",
        "Dockerfile",
    ]

    try:
        manifest_files = await detect_manifest_files(
            repository_files
        )

    except OllamaClientError as error:
        raise HTTPException(
            status_code=503,
            detail=str(error),
        ) from error

    return {
        "repository_file_count": len(repository_files),
        "manifest_count": len(manifest_files),
        "manifest_files": manifest_files,
    }


@app.get("/scan/{repository_name}")
async def scan(repository_name: str) -> dict:
    repository_name = repository_name.strip()

    if not repository_name:
        raise HTTPException(
            status_code=400,
            detail="Repository name cannot be empty.",
        )

    try:
        return await scan_repository(
            repository_name
        )

    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error),
        ) from error

    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=f"Repository scan failed: {error}",
        ) from error


def main() -> None:
    """
    Start the Repository Scanner Service.
    """
    scanner_service = services[
        "repository-scanner-service"
    ]

    uvicorn.run(
        app,
        host=scanner_service["host"],
        port=scanner_service["port"],
    )
