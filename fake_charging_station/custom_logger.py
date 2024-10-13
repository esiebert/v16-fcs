"""Module for custom logger."""

import logging


class CustomFormatter(logging.Formatter):
    """Custom log formatter."""

    grey = "\x1b[38;21m\x1b[24m"
    cyan = "\x1b[34;21m\x1b[24m"
    yellow = "\x1b[33;21m\x1b[24m"
    red = "\x1b[31;21m\x1b[24m"
    bold_red = "\x1b[31;1m\x1b[24m"
    reset = "\x1b[0m\x1b[24m"
    format_prefix = "%(asctime)s ["
    format_level = "%(levelname)s"
    format_sufix = ":%(name)s] %(message)s (%(filename)s:%(lineno)d)"

    FORMATS = {
        logging.DEBUG: format_prefix + grey + format_level + reset + format_sufix,
        logging.INFO: format_prefix + cyan + format_level + reset + " " + format_sufix,
        logging.WARNING: format_prefix + yellow + format_level + reset + format_sufix,
        logging.ERROR: format_prefix + red + format_level + reset + format_sufix,
        logging.CRITICAL: format_prefix + bold_red + format_level + reset + format_sufix,
    }

    def format(self, record) -> str:
        """Format a log message."""
        log_fmt = self.FORMATS.get(record.levelno)
        formatter = logging.Formatter(log_fmt, datefmt="%H:%M:%S")
        return formatter.format(record)


def get_logger(name: str) -> logging.Logger:
    """Get logger with custom formatter."""
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)

    stream_handler = logging.StreamHandler()
    stream_handler.setLevel(logging.INFO)
    stream_handler.setFormatter(CustomFormatter())

    logger.addHandler(stream_handler)
    return logger
