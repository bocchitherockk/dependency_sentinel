from logging import Logger

import uvicorn

from common.logging.global_logger import get_global_logger
from common.config import services

logger: Logger = get_global_logger(__name__)
logger.info('Starting Security Intelligence Service...')


def main() -> None:
    uvicorn.run(
        'security_intelligence_service.main:app',
        host=services['security-intelligence-service']['bind_host'],
        port=services['security-intelligence-service']['port'],
    )
