from logging import Logger

import uvicorn

from common.logging.global_logger import get_global_logger
from common.config import services

logger: Logger = get_global_logger(__name__)
logger.info('Starting LLM Service...')


def main() -> None:
    uvicorn.run(
        'llm_service.main:app',
        host=services['llm-service']['bind_host'],
        port=services['llm-service']['port'],
        reload=True,
    )
