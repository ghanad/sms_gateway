import logging
from pythonjsonlogger import jsonlogger


def configure_logging() -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(jsonlogger.JsonFormatter())
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.addHandler(handler)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
