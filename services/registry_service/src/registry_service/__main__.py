from logging import Logger
from common.logging.global_logger import get_global_logger

logger: Logger = get_global_logger(__name__)
logger.info("Starting Registry Service...")

from registry_service.main import main as registry_service_main

def main():
    registry_service_main()
