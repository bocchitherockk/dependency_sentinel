from datetime import datetime
import logging
from logging import Logger, FileHandler
import os
import sys

from common.logging.MyFormatter import MyFormatter

os.makedirs('./logs', exist_ok=True)

_file_handlers = {}

SESSION_HEADER = (
    "\n"
    + "=" * 80
    + "\n"
    + f"New execution: {datetime.now()}\n"
    + "=" * 80
    + "\n"
)

# TODO: `delete_previous_logs` this is wrong
def get_file_handler(path, delete_previous_logs: bool = False, write_session_header: bool = True) -> FileHandler:
    if path not in _file_handlers:
        if delete_previous_logs:
            _file_handlers[path] = logging.FileHandler(path, mode='w')
        else:
            if write_session_header:
                with open(path, 'a') as f:
                    f.write(SESSION_HEADER)
            _file_handlers[path] = logging.FileHandler(path, mode='a')

    return _file_handlers[path]

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

    # stdout_log_handler = logging.StreamHandler(sys.stdout)
    file_log_handler = get_file_handler(f'./logs/{microservice_name}.log')
    all_file_log_handler = get_file_handler(f'./logs/all.log', write_session_header=False)

    # stdout_log_handler  .setFormatter(MyFormatter(LOG_FORMAT_STRING, module_name=module_name, colorize=True))
    file_log_handler    .setFormatter(MyFormatter(LOG_FORMAT_STRING, module_name=module_name, colorize=False))
    all_file_log_handler.setFormatter(MyFormatter(LOG_FORMAT_STRING, module_name=module_name, colorize=False))

    # logger.addHandler(stdout_log_handler)
    logger.addHandler(file_log_handler)
    logger.addHandler(all_file_log_handler)
    return logger
