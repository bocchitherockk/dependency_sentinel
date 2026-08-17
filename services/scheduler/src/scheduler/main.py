from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Body
import uvicorn

from common.config import services
from common.schemas.StartScanRequest import StartScanRequest
from events import EventProducer
from events.schemas.ScanStartedEvent import ScanStartedEvent


event_producer: EventProducer = EventProducer()

@asynccontextmanager
async def lifespan(app: FastAPI):
    await event_producer.start()
    yield
    await event_producer.stop()

app = FastAPI(
    lifespan=lifespan,
)

@app.post('/start-scan')
async def start_scan_endpoint(start_scan_request: StartScanRequest = Body(...)):
    try:
        scan_started_event: ScanStartedEvent = ScanStartedEvent(
            key=start_scan_request.repository_url,
            repository_url=start_scan_request.repository_url,
        )
        await event_producer.publish(event=scan_started_event)

        # TODO: ideally, this should register a row in a database to track the scan status, and the response should include a unique scan ID.
        return {
            'status': 'accepted',
            'message': f'Scan process started for repository: {scan_started_event.repository_url}',
            'repository_url': scan_started_event.repository_url
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f'Failed to request scan: {str(e)}'
        )


def main() -> None:
    uvicorn.run(
        app,
        host=services['scheduler']['host'],
        port=services['scheduler']['port'],
    )
