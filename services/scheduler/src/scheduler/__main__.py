from scheduler.main import main as scheduler_main
from common.logging.global_logger import get_global_logger

logger = get_global_logger(__name__)

def main():
    logger.info('Starting the Scheduler service...')
    scheduler_main()

