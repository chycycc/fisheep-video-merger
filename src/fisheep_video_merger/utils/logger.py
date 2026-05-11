"""
日志模块
提供内存日志和文件日志功能
"""

import logging
import os
from datetime import datetime
from typing import Optional


class MemoryLogHandler(logging.Handler):
    """内存日志处理器，将日志保存在内存列表中"""

    def __init__(self, max_records: int = 1000):
        super().__init__()
        self.max_records = max_records
        self.records: list[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        """添加日志记录"""
        msg = self.format(record)
        self.records.append(msg)
        if len(self.records) > self.max_records:
            self.records.pop(0)

    def get_all(self) -> list[str]:
        """获取所有日志记录"""
        return list(self.records)

    def clear(self) -> None:
        """清空日志"""
        self.records.clear()


_logger: Optional[logging.Logger] = None
_memory_handler: Optional[MemoryLogHandler] = None


def setup_logger(log_dir: Optional[str] = None) -> logging.Logger:
    """
    初始化日志系统

    Args:
        log_dir: 日志文件目录，若为 None 则不写文件日志

    Returns:
        配置好的 Logger 实例
    """
    global _logger, _memory_handler

    if _logger is not None:
        return _logger

    _logger = logging.getLogger("fisheep_video_merger")
    _logger.setLevel(logging.DEBUG)

    formatter = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )

    # 内存日志
    _memory_handler = MemoryLogHandler()
    _memory_handler.setLevel(logging.DEBUG)
    _memory_handler.setFormatter(formatter)
    _logger.addHandler(_memory_handler)

    # 文件日志
    if log_dir:
        os.makedirs(log_dir, exist_ok=True)
        log_file = os.path.join(
            log_dir,
            f"merger_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log",
        )
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)
        _logger.addHandler(file_handler)

    return _logger


def get_logger() -> logging.Logger:
    """获取日志器实例"""
    global _logger
    if _logger is None:
        return setup_logger()
    return _logger


def get_logs() -> list[str]:
    """获取所有内存日志"""
    global _memory_handler
    if _memory_handler is None:
        return []
    return _memory_handler.get_all()


def clear_logs() -> None:
    """清空内存日志"""
    global _memory_handler
    if _memory_handler is not None:
        _memory_handler.clear()
