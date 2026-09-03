from logging import Logger
from common.logging.global_logger import get_global_logger

logger: Logger = get_global_logger(__name__)
logger.info('Starting Repository Scanner Service...')

from repository_scanner_service.main import main as repository_scanner_service_main

def main():
    repository_scanner_service_main()
