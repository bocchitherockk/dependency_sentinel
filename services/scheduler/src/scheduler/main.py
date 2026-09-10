import asyncio
from contextlib import asynccontextmanager
from logging import Logger
from pathlib import Path

from fastapi import FastAPI

from common.logging.global_logger import get_global_logger

from scheduler.utils import (
    load_scan_schedule,
    schedule_periodic_scan,
)
from scheduler.schemas.RepositoryScanSchedule import RepositoryScanSchedule

logger: Logger = get_global_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    background_tasks: list[asyncio.Task] = []
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


app = FastAPI(
    title='Scheduler',
    description='A service that schedules scans for repositories based on a predefined schedule or on-demand requests.',
    version='0.1.0',
    lifespan=lifespan,
)
