from logging import Logger

import uvicorn

from common.logging.global_logger import get_global_logger
from common.config import services

logger: Logger = get_global_logger(__name__)
logger.info("Starting Registry Service...")


def main() -> None:
    uvicorn.run(
        'registry_service.main:app',
        host=services['registry-service']['bind_host'],
        port=services['registry-service']['port'],
        reload=True,
    )
