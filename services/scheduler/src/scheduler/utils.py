import json
from logging import Logger
from pathlib import Path

from common.logging.global_logger import get_global_logger

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
