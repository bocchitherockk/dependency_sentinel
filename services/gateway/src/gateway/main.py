from fastapi import FastAPI, HTTPException

from common.schemas.StartScanRequest import StartScanRequest

from gateway.service import start_scan_service

app = FastAPI(
    title="Gateway Service",
    description="Single entry point for the platform",
    version="0.2.0",
)

@app.post('/start-scan')
async def start_scan_endpoint(start_scan_request: StartScanRequest):
    try:
        return await start_scan_service(start_scan_request)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
