import httpx

from common.config import services
from common.schemas.StartScanRequest import StartScanRequest
from common.schemas.CloneRepositoryRequest import CloneRepositoryRequest

async def start_scan_service(start_scan_request: StartScanRequest):
    clone_repository_request: CloneRepositoryRequest = CloneRepositoryRequest(
        repository_url=start_scan_request.repository_url,
    )
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{services['repository-storage-service']['endpoint']}/clone-repository",
                json=clone_repository_request.model_dump(mode='json'),
            )
        response.raise_for_status()
        return response.json()
    except Exception as e:
        raise RuntimeError(f"Failed to start scan for repository {start_scan_request.repository_url}: {str(e)}") from e
