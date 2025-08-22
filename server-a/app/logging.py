import logging
from pythonjsonlogger import jsonlogger
import sys
from typing import Optional

class CustomJsonFormatter(jsonlogger.JsonFormatter):
    def add_fields(self, log_record, record, message_dict):
        super().add_fields(log_record, record, message_dict)
        if not log_record.get('service'):
            log_record['service'] = 'server-a'
        if not log_record.get('level'):
            log_record['level'] = record.levelname
        if not log_record.get('timestamp'):
            log_record['timestamp'] = self.formatTime(record, self.datefmt)
        if 'message' not in log_record:
            log_record['message'] = record.getMessage()

        # Add tracking_id and client_api_key if available in extra
        if hasattr(record, 'tracking_id'):
            log_record['tracking_id'] = record.tracking_id
        if hasattr(record, 'client_api_key'):
            log_record['client_api_key'] = record.client_api_key

def setup_logging(level: str = "INFO"):
    logger = logging.getLogger()
    logger.setLevel(level)

    # Remove existing handlers to prevent duplicate logs in some environments (e.g., Gunicorn)
    if logger.handlers:
        for handler in logger.handlers:
            logger.removeHandler(handler)

    handler = logging.StreamHandler(sys.stdout)
    formatter = CustomJsonFormatter(
        '%(timestamp)s %(level)s %(service)s %(message)s %(tracking_id)s %(client_api_key)s'
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)

    # Configure uvicorn's access logger to use our JSON formatter
    uvicorn_access_logger = logging.getLogger("uvicorn.access")
    uvicorn_access_logger.handlers.clear() # Clear default handlers
    uvicorn_access_logger.addHandler(handler)
    uvicorn_access_logger.propagate = False # Prevent logs from going to root logger again

    # Configure uvicorn's error logger to use our JSON formatter
    uvicorn_error_logger = logging.getLogger("uvicorn.error")
    uvicorn_error_logger.handlers.clear() # Clear default handlers
    uvicorn_error_logger.addHandler(handler)
    uvicorn_error_logger.propagate = False # Prevent logs from going to root logger again

# Example usage (can be called from main.py)
if __name__ == "__main__":
    setup_logging("DEBUG")
    logger = logging.getLogger(__name__)
    logger.info("This is a test log message.")
    logger.warning("This is a warning with extra fields.", extra={'tracking_id': '123-abc', 'client_api_key': 'test-client'})
    logger.error("An error occurred.")