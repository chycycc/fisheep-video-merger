"""
格式转换模块
支持视频文件格式转换（流复制或重编码）
"""

import os
from typing import Callable, Optional

from fisheep_video_merger.core.ffmpeg_runner import run_ffmpeg, ensure_output_dir, get_ffmpeg_path, get_hw_encoder


def convert_single(
    input_file: str,
    output_path: str,
    mode: str = "copy",
    progress_callback: Optional[Callable] = None,
) -> tuple[bool, Optional[str]]:
    """
    转换单个视频文件格式

    Args:
        input_file: 输入文件路径
        output_path: 输出文件路径
        mode: "copy"（流复制，快速无损）或 "recode"（重编码）
        progress_callback: 进度回调

    Returns:
        (成功标志, 错误信息)
    """
    err = ensure_output_dir(output_path)
    if err:
        return False, err

    if mode == "copy":
        cmd = [
            get_ffmpeg_path(),
            "-i", input_file,
            "-c", "copy",
            "-y", output_path,
        ]
    else:
        # 优先使用硬件加速编码器
        hw_encoder = get_hw_encoder()
        video_codec = hw_encoder if hw_encoder else "libx264"
        cmd = [
            get_ffmpeg_path(),
            "-i", input_file,
            "-c:v", video_codec,
            "-c:a", "aac",
            "-y", output_path,
        ]

    if progress_callback:
        progress_callback(f"正在转换: {os.path.basename(output_path)}")

    return run_ffmpeg(cmd, output_path, progress_callback, "转换")
