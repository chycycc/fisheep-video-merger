"""
B站元数据模块
负责读取 B站缓存目录的 entry.json 元数据
"""

import json
import os
from typing import Optional


def read_bilibili_meta(source_dir: str) -> Optional[dict]:
    """
    读取 B站缓存目录的 entry.json 元数据（可选增强）
    向上查找最多 3 级目录，非 B站目录返回 None
    """
    for _ in range(3):
        entry_path = os.path.join(source_dir, "entry.json")
        if os.path.isfile(entry_path):
            try:
                with open(entry_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, OSError):
                pass
        parent = os.path.dirname(source_dir)
        if parent == source_dir:
            break
        source_dir = parent
    return None
