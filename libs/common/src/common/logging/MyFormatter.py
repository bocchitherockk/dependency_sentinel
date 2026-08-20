import logging

class MyFormatter(logging.Formatter):
    GREY       = '\x1b[38;21m'
    BLUE       = '\x1b[38;5;39m'
    GREEN      = '\x1b[38;5;46m'
    DARK_GREEN = '\x1b[38;5;28m'
    YELLOW     = '\x1b[38;5;226m'
    RED        = '\x1b[38;5;196m'
    BOLD_RED   = '\x1b[31;1m'
    RESET      = '\x1b[0m'

    # Define styles for each log level
    LEVEL_COLORS = {
        logging.DEBUG:    BLUE,
        logging.INFO:     DARK_GREEN,
        logging.WARNING:  YELLOW,
        logging.ERROR:    RED,
        logging.CRITICAL: BOLD_RED
    }
    
    def __init__(self, fmt, module_name: str, colorize: bool = True):
        self.module_name: str = module_name
        self.colorize: bool = colorize
        super().__init__(fmt)

    def format(self, record):
        if not self.colorize:
            result = super().format(record)
            result = result.format(module_name=self.module_name)
            return result

        else:
            # Fetch the color code corresponding to the log level
            color_code = self.LEVEL_COLORS.get(record.levelno, self.RESET)
            # Override the levelname with the colored version
            orig_levelname = record.levelname
            record.levelname = f'{color_code}{orig_levelname}{self.RESET}'
            # Call the original formatter logic
            result = super().format(record)
            result = result.format(module_name=self.module_name)
            # Restore the original levelname so downstream handlers (like file logs) stay clean
            record.levelname = orig_levelname
            return result
