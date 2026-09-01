"""项目日志配置：控制台 + 按大小轮转的文件日志。"""

import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path


BASE_PATH = Path(__file__).resolve().parent.parent
LOG_PATH = Path(os.getenv("AXCOIN_LOG_DIR", BASE_PATH / "log"))
LOG_FORMAT = "[%(asctime)s][%(filename)s %(lineno)d][%(levelname)s]: %(message)s"


def build_logger(name="axcoin", level=None):
    """创建一次 logger；重复导入不会添加重复 Handler。"""
    target = logging.getLogger(name)
    target.setLevel(level or os.getenv("AXCOIN_LOG_LEVEL", "INFO").upper())
    target.propagate = False
    if target.handlers:
        return target
    formatter = logging.Formatter(LOG_FORMAT)
    console = logging.StreamHandler()
    console.setFormatter(formatter)
    target.addHandler(console)
    try:
        LOG_PATH.mkdir(parents=True, exist_ok=True)
        file_handler = RotatingFileHandler(
            LOG_PATH / "axcoin.log",
            maxBytes=10 * 1024 * 1024,
            backupCount=5,
            encoding="utf-8",
        )
        file_handler.setFormatter(formatter)
        target.addHandler(file_handler)
    except OSError as error:
        target.warning("无法创建文件日志，仅使用控制台日志: %s", error)
    return target


class Logger:
    """兼容原项目 ``Logger().logger`` 用法。"""
    def __init__(self):
        self.logger = build_logger()


logger = build_logger()


if __name__ == "__main__":
    logger.info("logger ready")
