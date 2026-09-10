from logging import Logger

import uvicorn

from common.logging.global_logger import get_global_logger
from common.config import services

logger: Logger = get_global_logger(__name__)
logger.info('Starting Scheduler service...')


def main() -> None:
    uvicorn.run(
        'scheduler.main:app',
        host=services['scheduler']['bind_host'],
        port=services['scheduler']['port'],
        reload=True,
    )
