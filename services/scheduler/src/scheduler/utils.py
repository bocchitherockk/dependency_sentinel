import asyncio
import json
from logging import Logger
from pathlib import Path

import httpx

from common.config import services
from common.logging.global_logger import get_global_logger
from common.schemas.StartScanRequest import StartScanRequest

from scheduler.schemas.RepositoryScanSchedule import RepositoryScanSchedule

logger: Logger = get_global_logger(__name__)

def load_scan_schedule(path: Path) -> list[RepositoryScanSchedule]:
    if not path.exists():
        logger.warning(f"Scan scheduler file not found: '{path}'.")
        return []

    with path.open('r') as f:
        try:
            schedule: list[dict[str, str | int]] = json.load(f)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to decode scan scheduler as JSON from '{path}': {str(e)}")
            logger.debug(f'File content: {f.read()}')
            return []

        result: list[RepositoryScanSchedule] = [
            RepositoryScanSchedule(**scan)
            for scan in schedule
        ]
        logger.info(f'Successfully loaded scan schedule from {path}.')
        logger.debug(f'Scan schedule content: {result}')
        return result

async def schedule_periodic_scan(repository_url: str, interval_seconds: float) -> None:
    logger.info(f'Scheduling periodic scan for {repository_url} every {interval_seconds} seconds.')
    while True:
        try:
            start_scan_request: StartScanRequest = StartScanRequest(
                repository_url=repository_url,
            )
            logger.info(f"Scan started for repository '{repository_url}'.")
            with httpx.AsyncClient() as client:
                response = await client.post(
                    f'http://{services["gateway"]["endpoint"]}/start-scan',
                    json=start_scan_request.model_dump(mode='json'),
                )
                response.raise_for_status()
        except Exception as e:
            logger.error(f"Failed to start scan for repository '{repository_url}': {str(e)}")

        logger.info(f'Waiting for {interval_seconds} seconds before the next scan for {repository_url}.')
        await asyncio.sleep(interval_seconds)
