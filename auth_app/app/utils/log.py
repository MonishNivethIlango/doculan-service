from __future__ import annotations
import os
from typing import TYPE_CHECKING
from loguru import logger

if TYPE_CHECKING:
    import loguru

class Logger:
    def log(self) -> loguru.Logger:
        logger.remove()
        logger.add(
            lambda msg: print(msg, end=""),
            level='INFO',
            filter=lambda record: record['level'].name == 'INFO' or record['level'].no <= 25,
            backtrace=False,
            diagnose=False,
        )

        logger.add(
            lambda msg: print(msg, end=""),
            level='ERROR',
            filter=lambda record: record['level'].name == 'ERROR' or record['level'].no >= 30,
            backtrace=True,
            diagnose=True,
        )

        return logger


log = Logger().log()