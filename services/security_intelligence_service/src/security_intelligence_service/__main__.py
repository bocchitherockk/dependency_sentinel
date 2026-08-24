from logging import Logger
from common.logging.global_logger import get_global_logger

logger: Logger = get_global_logger(__name__)
logger.info('Starting Security Intelligence Service...')

from security_intelligence_service.main import main as security_intelligence_service_main

def main():
    security_intelligence_service_main()
