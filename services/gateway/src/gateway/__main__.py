from logging import Logger

import uvicorn

from common.config import services
from common.logging.global_logger import get_global_logger

logger: Logger = get_global_logger(__name__)
logger.info('Starting Gateway...')


def main():
    uvicorn.run(
        'gateway.main:app',
        host=services['gateway']['bind_host'],
        port=services['gateway']['port'],
    )
