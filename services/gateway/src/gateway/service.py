import httpx

from common.config import services
from common.schemas.StartScanRequest import StartScanRequest

async def start_scan_service(start_scan_request: StartScanRequest):
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{services['repository-storage-service']['endpoint']}/start-scan",
                json=start_scan_request.model_dump(mode='json'),
            )
        response.raise_for_status()
        return response.json()
    except Exception as e:
        raise RuntimeError(f"Failed to start scan for repository '{start_scan_request.repository_url}': {str(e)}") from e
