from logging import Logger
from common.logging.global_logger import get_global_logger

logger: Logger = get_global_logger(__name__)
logger.info('Starting LLM Service...')

from llm_service.main import main as llm_service_main

def main():
    llm_service_main()
