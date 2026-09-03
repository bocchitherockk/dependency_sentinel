from logging import Logger
from common.logging.global_logger import get_global_logger
logger: Logger = get_global_logger(__name__)

logger.info('Starting Repository Storage Service...')

from repository_storage_service.main import main as repository_storage_service_main

def main():
    repository_storage_service_main()
