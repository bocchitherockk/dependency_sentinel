import asyncio
from contextlib import asynccontextmanager
from logging import Logger
from pathlib import Path

from fastapi import FastAPI, HTTPException, Body
import uvicorn

from common.logging.global_logger import get_global_logger
from common.config import services
from common.schemas.StartScanRequest import StartScanRequest
from events import EventProducer
from events.schemas.ScanStartedEvent import ScanStartedEvent

from scheduler.utils import load_scan_schedule
from scheduler.schemas.RepositoryScanSchedule import RepositoryScanSchedule

logger: Logger = get_global_logger(__name__)

event_producer: EventProducer = EventProducer()

async def schedule_periodic_scan(repository_url: str, interval_seconds: float) -> None:
    logger.info(f'Scheduling periodic scan for {repository_url} every {interval_seconds} seconds.')
    while True:
        try:
            scan_started_event: ScanStartedEvent = ScanStartedEvent(
                key=repository_url,
                repository_url=repository_url,
            )
            logger.info(f'Publishing ScanStartedEvent for {repository_url}.')
            await event_producer.publish(event=scan_started_event)
        except Exception as e:
            logger.error(f'Failed to publish scan started event for {repository_url}: {str(e)}')

        logger.info(f'Waiting for {interval_seconds} seconds before the next scan for {repository_url}.')
        await asyncio.sleep(interval_seconds)

@asynccontextmanager
async def lifespan(app: FastAPI):
    background_tasks: list[asyncio.Task] = []
    await event_producer.start()
    schedule: list[RepositoryScanSchedule] = load_scan_schedule(Path('./services/scheduler/scan_schedule.json'))
    for repository_scan_schedule in schedule:
        background_tasks.append(asyncio.create_task(
            schedule_periodic_scan(
                repository_url=repository_scan_schedule.repository_url,
                interval_seconds=repository_scan_schedule.interval_seconds,
            )
        ))

    yield

    for task in background_tasks:
        task.cancel()
    await asyncio.gather(*background_tasks, return_exceptions=True)
    await event_producer.stop()

app = FastAPI(
    title='Scheduler',
    description='A service that schedules scans for repositories based on a predefined schedule or on-demand requests.',
    version='0.1.0',
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
        logger.info(f'Successfully published ScanStartedEvent for {start_scan_request.repository_url}.')

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
        host=services['scheduler']['bind_host'],
        port=services['scheduler']['port'],
    )
