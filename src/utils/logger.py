"""
Logging configuration.
Usage anywhere in the project:
    from src.utils.logger import logger
    logger.info("Something happened")
    logger.error("Something broke")
"""

from loguru import logger
import sys
from pathlib import Path

LOG_DIR = Path(__file__).parent.parent.parent / "logs"
LOG_DIR.mkdir(exist_ok=True)

logger.remove()

logger.add(
    sys.stderr,
    format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan> - <level>{message}</level>",
    level="INFO"
)

logger.add(
    LOG_DIR / "pipeline_{time:YYYY-MM-DD}.log",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name} - {message}",
    level="DEBUG",
    rotation="1 day",
    retention="30 days"
)

