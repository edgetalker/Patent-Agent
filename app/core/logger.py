import logging
import sys
from typing import Optional


def setup_logger(name: str, level: Optional[int] = None) -> logging.Logger:
    """
    返回统一格式的 logger。
    - 格式：时间 | 级别 | 模块名 | 消息
    - 避免重复 handler（多次 import 安全）
    """
    logger = logging.getLogger(name)

    if logger.handlers:
        return logger

    if level is None:
        from app.config import get_settings
        level = logging.DEBUG if get_settings().debug else logging.INFO

    logger.setLevel(level)

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(level)
    handler.setFormatter(
        logging.Formatter(
            fmt="%(asctime)s | %(levelname)-8s | %(name)-28s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )
    logger.addHandler(handler)
    logger.propagate = False
    return logger


# 默认全局 logger，其他模块直接 from app.core.logger import logger
logger = setup_logger("patent_agent")