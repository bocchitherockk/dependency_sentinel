import uvicorn
from fastapi import FastAPI, HTTPException

from common.config import services
from repository_scanner_service.utils import scan_repository


app = FastAPI(
    title="Repository Scanner Service",
    description=(
        "Scans repositories, detects dependency manifest files "
        "with the LLM Service, and extracts their dependencies."
    ),
    version="0.2.0",
)

@app.get("/scan/{repository_name}")
async def scan(repository_name: str):
    repository_name = repository_name.strip()

    if not repository_name:
        raise HTTPException(
            status_code=400,
            detail="Repository name cannot be empty.",
        )

    try:
        return await scan_repository(repository_name)
    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=f"Repository scan failed: {error}",
        ) from error


def main() -> None:
    """
    Start the Repository Scanner Service.
    """

    scanner_service = services['repository-scanner-service']
    uvicorn.run(
        app,
        host=scanner_service["host"],
        port=scanner_service["port"],
    )