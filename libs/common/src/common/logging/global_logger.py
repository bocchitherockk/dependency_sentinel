import logging
from logging import Logger
import os
import sys

from common.logging.MyFormatter import MyFormatter

os.makedirs('./logs', exist_ok=True)

LOG_FORMAT_STRING = '[%(levelname)s]: %(asctime)s - {module_name} - %(message)s'

def get_global_logger(module_name: str, logging_level: int = logging.DEBUG) -> Logger:
    microservice_name = module_name.split('.')[0]

    is_new_logger: bool = False
    if module_name not in logging.Logger.manager.loggerDict:
        is_new_logger = True

    logger: Logger = logging.getLogger(module_name)
    if not is_new_logger:
        return logger

    logger.setLevel(logging_level)

    stdout_log_handler = logging.StreamHandler(sys.stdout)
    file_log_handler = logging.FileHandler(
        f'./logs/{microservice_name}.log',
        mode='a'
    )

    stdout_log_handler.setFormatter(MyFormatter(LOG_FORMAT_STRING, module_name=module_name, colorize=True))
    file_log_handler  .setFormatter(MyFormatter(LOG_FORMAT_STRING, module_name=module_name, colorize=False))

    logger.addHandler(stdout_log_handler)
    logger.addHandler(file_log_handler)
    return logger
