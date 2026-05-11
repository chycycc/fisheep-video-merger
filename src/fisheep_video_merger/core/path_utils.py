"""
路径工具模块
负责生成输出文件路径（扁平输出到指定目录）
"""

import os


def generate_output_path(
    output_root: str,
    source_dir: str,
    root_path: str,
    output_name: str,
    output_format: str,
) -> str:
    """
    生成最终的输出文件路径

    所有文件直接输出到 output_root 目录下，不保留源目录结构。

    Args:
        output_root: 输出根目录
        source_dir: 源文件所在目录（保留参数但不使用）
        root_path: 拖入根目录（保留参数但不使用）
        output_name: 输出文件名（不含扩展名）
        output_format: 输出格式（mp4/mkv/mov/flv）

    Returns:
        完整的输出文件路径
    """
    # 确保扩展名正确
    ext = output_format.lower().lstrip(".")
    filename = f"{output_name}.{ext}"

    return os.path.join(output_root, filename)
