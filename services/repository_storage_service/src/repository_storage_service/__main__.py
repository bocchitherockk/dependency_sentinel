from logging import Logger

import uvicorn

from common.config import services
from common.logging.global_logger import get_global_logger

logger: Logger = get_global_logger(__name__)

logger.info('Starting Repository Storage Service...')

def main() -> None:
    uvicorn.run(
        'repository_storage_service.main:app',
        host=services['repository-storage-service']['bind_host'],
        port=services['repository-storage-service']['port'],
        reload=True,
    )
