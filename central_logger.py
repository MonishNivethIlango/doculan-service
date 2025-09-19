import logging
import os

LOG_FILE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'logs', 'app.log')

os.makedirs(os.path.dirname(LOG_FILE_PATH), exist_ok=True)

class CentralLogger:
    _logger = None

    @classmethod
    def get_logger(cls, name: str = "doculan_app"):
        if cls._logger is None:
            cls._logger = logging.getLogger(name)
            cls._logger.setLevel(logging.INFO)

            # Prevent duplicate handlers
            if not cls._logger.handlers:
                file_handler = logging.FileHandler(LOG_FILE_PATH)
                formatter = logging.Formatter(
                    '%(asctime)s | %(levelname)s | %(name)s | %(message)s'
                )
                file_handler.setFormatter(formatter)
                cls._logger.addHandler(file_handler)

        return cls._logger