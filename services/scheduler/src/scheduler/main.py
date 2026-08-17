import asyncio
from contextlib import asynccontextmanager
import os
from pathlib import Path

from fastapi import FastAPI, HTTPException, Body
import uvicorn

from common.config import services
from common.schemas.StartScanRequest import StartScanRequest
from events import EventProducer
from events.schemas.ScanStartedEvent import ScanStartedEvent

from scheduler.utils import load_scan_schedule

os.chdir('./services/scheduler/') # change current working directory

event_producer: EventProducer = EventProducer()
background_tasks: list[asyncio.Task] = []

async def schedule_periodic_scan(repository_url: str, interval_seconds: float) -> None:
    while True:
        try:
            scan_started_event = ScanStartedEvent(
                key=repository_url,
                repository_url=repository_url,
            )
            await event_producer.publish(event=scan_started_event)
        except Exception as e:
            print(f"Failed to publish scheduled scan for {repository_url}: {e}")

        await asyncio.sleep(interval_seconds)

@asynccontextmanager
async def lifespan(app: FastAPI):
    await event_producer.start()
    schedule = load_scan_schedule(Path('scan_schedule.json'))
    for record in schedule:
        task = asyncio.create_task(
            schedule_periodic_scan(
                repository_url=record['repository_url'],
                interval_seconds=float(record['time_interval']),
            )
        )
        background_tasks.append(task)

    yield

    for task in background_tasks:
        task.cancel()
    await asyncio.gather(*background_tasks, return_exceptions=True)
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
