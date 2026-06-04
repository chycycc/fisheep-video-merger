"""
命名模块
负责智能输出文件名生成和命名模板应用
"""

import os
import re
from typing import Optional

from fisheep_video_merger.core.episode import extract_episode_number, normalize_episode_name
from fisheep_video_merger.core.bilibili import read_bilibili_meta


def suggest_output_name(video_filepath: str, source_dir: str, root_path: str) -> str:
    """
    智能生成输出文件名
    优先级：平台元数据（如 B站 entry.json）> 父目录名 + 集数 > 文件名
    """
    # 1. 尝试读取平台元数据
    meta = read_bilibili_meta(source_dir)
    if meta:
        series_title = meta.get("title", "")
        ep_info = meta.get("ep", {})
        ep_index = ep_info.get("index", "")
        ep_title = ep_info.get("index_title", "")

        if series_title:
            series_title = re.sub(r'[\\/:*?"<>|]', "", series_title).strip()
            if ep_index:
                try:
                    return f"{series_title}_{int(ep_index):02d}"
                except (ValueError, TypeError):
                    pass
            if ep_title:
                ep_title = re.sub(r'[\\/:*?"<>|]', "", ep_title).strip()
                return f"{series_title}_{ep_title}"
            else:
                return series_title

    # 2. 从父目录名提取系列名
    parent_name = os.path.basename(source_dir)
    if re.match(r"^\d+$", parent_name):
        grandparent = os.path.dirname(source_dir)
        gp_name = os.path.basename(grandparent)
        if gp_name and not re.match(r"^\d+$", gp_name) and gp_name != os.path.basename(root_path):
            parent_name = gp_name

    # 3. 父目录名 + 文件集数
    ep = extract_episode_number(os.path.basename(video_filepath))
    if ep is not None:
        parent_clean = re.sub(r'[\\/:*?"<>|]', "", parent_name).strip()
        if parent_clean and not re.match(r"^\d+$", parent_clean):
            return f"{parent_clean}_{ep:02d}"
        return f"E{ep:02d}"

    # 4. 兜底：纯文件名
    return normalize_episode_name(video_filepath)


def apply_naming_template(template: str, video_filepath: str, source_dir: str, root_path: str, index: int = 0) -> str:
    """
    应用命名模板生成输出文件名

    支持变量：
        {series} — 系列名（从 B站元数据或父目录提取）
        {ep} — 集数（默认2位补零，支持 {ep:03d} 等格式化语法）
        {original} — 原始文件名（不含扩展名）
        {index} — 序号（从1开始）

    Args:
        template: 模板字符串，如 "{series}_{ep}" 或 "{series}_{ep:03d}"
        video_filepath: 视频文件路径
        source_dir: 源目录
        root_path: 根目录
        index: 任务序号

    Returns:
        格式化后的输出文件名（不含扩展名）
    """
    if not template or not template.strip():
        return suggest_output_name(video_filepath, source_dir, root_path)

    # 提取变量值
    meta = read_bilibili_meta(source_dir)
    series = ""
    ep_num = None
    if meta:
        series = re.sub(r'[\\/:*?"<>|]', "", meta.get("title", "")).strip()
        ep_info = meta.get("ep", {})
        ep_raw = ep_info.get("index", "")
        if ep_raw:
            try:
                ep_num = int(ep_raw)
            except (ValueError, TypeError):
                pass

    if not series:
        parent_name = os.path.basename(source_dir)
        if re.match(r"^\d+$", parent_name):
            grandparent = os.path.dirname(source_dir)
            gp_name = os.path.basename(grandparent)
            if gp_name and not re.match(r"^\d+$", gp_name) and gp_name != os.path.basename(root_path):
                parent_name = gp_name
        series = re.sub(r'[\\/:*?"<>|]', "", parent_name).strip()

    if ep_num is None:
        ep_num = extract_episode_number(os.path.basename(video_filepath))

    # {ep} 默认格式为2位补零，保持向后兼容
    ep_default = f"{ep_num:02d}" if ep_num is not None else ""
    original = os.path.splitext(os.path.basename(video_filepath))[0]

    # 先处理 {ep:FORMAT} 格式化语法（如 {ep:03d}、{ep:02d}）
    def _replace_ep_format(match: re.Match) -> str:
        fmt = match.group(1)
        if ep_num is not None:
            try:
                return format(ep_num, fmt)
            except (ValueError, TypeError):
                return ep_default
        return ep_default

    result = re.sub(r"\{ep:([^}]+)}", _replace_ep_format, template)
    result = result.replace("{series}", series)
    result = result.replace("{ep}", ep_default)
    result = result.replace("{original}", original)
    result = result.replace("{index}", str(index + 1))

    result = re.sub(r"[_\s]+", "_", result).strip("_- .")
    return result if result else normalize_episode_name(video_filepath)
