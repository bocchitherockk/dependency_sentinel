from logging import Logger
from common.logging.global_logger import get_global_logger

logger: Logger = get_global_logger(__name__)
logger.info('Starting Gateway...')

from gateway.main import main as gateway_main

def main():
    gateway_main()
