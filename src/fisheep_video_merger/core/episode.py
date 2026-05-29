"""
集数提取模块
从文件名中提取集数信息，支持中文数字、EP/P/Part 等多种格式
"""

import os
import re
from typing import Optional, List, Tuple, Callable


# 中文数字映射
_CN_NUM_MAP = {
    "零": 0, "一": 1, "二": 2, "两": 2, "三": 3, "四": 4,
    "五": 5, "六": 6, "七": 7, "八": 8, "九": 9,
    "十": 10, "百": 100, "千": 1000,
}


def _parse_chinese_number(text: str) -> Optional[int]:
    """
    将中文数字字符串转换为阿拉伯数字

    Args:
        text: 中文数字，如 "三"、"十二"、"二十五"、"一百"

    Returns:
        阿拉伯数字，或 None 如果无法解析
    """
    if not text:
        return None

    if text in _CN_NUM_MAP:
        val = _CN_NUM_MAP[text]
        if val < 10:
            return val

    total = 0
    current = 0
    for char in text:
        if char in _CN_NUM_MAP:
            num = _CN_NUM_MAP[char]
            if num >= 10:
                if current == 0:
                    current = 1
                total += current * num
                current = 0
            else:
                current = num
        else:
            return None
    total += current

    return total if total > 0 else None


# 声明式集数匹配与清理配置（正则已预编译）
# 元组格式: (编译后的匹配正则, 提取处理器函数, 编译后的清理正则)
_EPISODE_PATTERNS: List[Tuple[re.Pattern, Callable[[re.Match], Optional[int]], re.Pattern]] = [
    (
        re.compile(r"第\s*(\d+)\s*[集话篇幕次期回P]", re.IGNORECASE),
        lambda m: int(m.group(1)),
        re.compile(r"第\s*\d+\s*[集话篇幕次期回P]", re.IGNORECASE),
    ),
    (
        re.compile(r"第\s*([零一二两三四五六七八九十百千]+)\s*[集话篇幕次期回]"),
        lambda m: _parse_chinese_number(m.group(1)),
        re.compile(r"第\s*[零一二两三四五六七八九十百千]+\s*[集话篇幕次期回]"),
    ),
    (
        re.compile(r"(?:EP|Ep|ep|Part|part|P|p)\s*(\d+)", re.IGNORECASE),
        lambda m: int(m.group(1)),
        re.compile(r"(?:EP|Ep|ep|Part|part|P|p)\s*\d+", re.IGNORECASE),
    ),
    (
        re.compile(r"(?<![a-zA-Z])E\s*(\d+)", re.IGNORECASE),
        lambda m: int(m.group(1)),
        re.compile(r"(?<![a-zA-Z])E\s*\d+", re.IGNORECASE),
    ),
    (
        re.compile(r"#\s*(\d+)"),
        lambda m: int(m.group(1)),
        re.compile(r"#\s*\d+"),
    ),
    (
        re.compile(r"[\(\[【]\s*(\d+)\s*[\)\]】]"),
        lambda m: int(m.group(1)),
        re.compile(r"[\(\[【]\s*\d+\s*[\)\]】]"),
    ),
    (
        re.compile(r"^(\d{1,4})[\s._-]+"),
        lambda m: int(m.group(1)),
        re.compile(r"^[\s._-]*\d+[\s._-]+"),
    ),
    (
        re.compile(r"[-_\s]+(\d{2,})$"),
        lambda m: int(m.group(1)),
        re.compile(r"[-_\s]+\d{2,}$"),
    ),
]


def extract_episode_number(filename: str) -> Optional[int]:
    """
    从文件名中提取集数

    支持以下模式（不区分大小写）：
    - `第3集`, `第03话`, `第3幕`
    - `第两百集`, `第十二话`
    - `EP03`, `EP3`, `Ep03`
    - `Part 1`, `part 01`, `P1`, `p02`
    - `E03`, `e3`
    - `#03`, `#3`
    - `(03)`, `[3]`, `【03】`
    - `01.xxx` (前缀序号模式)
    - `03` (纯数字作为文件名末尾或倒数第二部分)

    Args:
        filename: 文件名（不含路径）

    Returns:
        集数（从 1 开始），如果未找到则返回 None
    """
    name, _ = os.path.splitext(filename)
    for pattern, processor, _ in _EPISODE_PATTERNS:
        m = pattern.search(name)
        if m:
            val = processor(m)
            if val is not None:
                return val
    return None


def normalize_episode_name(video_filename: str) -> str:
    """
    根据视频文件名智能生成输出文件名

    如果文件名中包含集数信息，则提取集数并格式化为 _NN（2位）。

    Args:
        video_filename: 视频文件完整路径

    Returns:
        输出文件名（不含扩展名）
    """
    basename = os.path.basename(video_filename)
    name_without_ext, _ = os.path.splitext(basename)

    ep = extract_episode_number(basename)
    if ep is not None:
        clean = name_without_ext
        for _, _, clean_pat in _EPISODE_PATTERNS:
            clean = clean_pat.sub("", clean)
        clean = clean.strip("-_ .")

        if clean:
            clean = re.sub(r"[-_\s]+", "_", clean).strip("_")
            return f"{clean}_{ep:02d}"
        else:
            return f"E{ep:02d}"

    return name_without_ext


def get_clean_episode_patterns() -> List[Tuple[re.Pattern, Callable, re.Pattern]]:
    """返回预编译的集数模式列表（供 matcher 策略使用）"""
    return _EPISODE_PATTERNS
