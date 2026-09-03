from fastapi import FastAPI
import uvicorn
import httpx

from common.config import services
from common.schemas.StartScanRequest import StartScanRequest


app = FastAPI(
    title="Gateway Service",
    description="Single entry point for the platform",
    version="0.2.0",
)

@app.post('/start-scan')
async def start_scan_endpoint(start_scan_request: StartScanRequest):
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{services['scheduler']['endpoint']}/start-scan",
            json=start_scan_request.model_dump(mode='json'),
        )
    response.raise_for_status()
    return response.json()


def main():
    uvicorn.run(
        app,
        host=services['gateway']['host'],
        port=services['gateway']['port'],
    )
