import uvicorn
from fastapi import FastAPI, HTTPException

from repository_scanner_service.scanner import scan_repository
from common.config import services

app = FastAPI(
    title="Repository Scanner Service",
    description="Scans repositories and extracts their dependencies.",
    version="0.1.0",
)


@app.get("/")
def home() -> dict[str, str]:
    return {
        "service": "repository-scanner-service",
        "message": "Repository Scanner Service is running.",
    }


@app.get("/scan/{repository_name}")
def scan(repository_name: str) -> dict:
    repository_name = repository_name.strip()

    if not repository_name:
        raise HTTPException(
            status_code=400,
            detail="Repository name cannot be empty.",
        )

    try:
        return scan_repository(repository_name)

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
    uvicorn.run(
        app,
        host=services['repository-scanner-service']['host'],
        port=services['repository-scanner-service']['port'],
    )
