from logging import Logger
from common.logging.global_logger import get_global_logger

logger: Logger = get_global_logger(__name__)
logger.info('Starting Scheduler service...')

from scheduler.main import main as scheduler_main

def main():
    scheduler_main()
