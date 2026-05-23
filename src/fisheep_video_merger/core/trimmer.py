"""
视频裁剪模块
按起止时间截取视频片段
"""

import os
import re
from typing import Callable, Optional

from fisheep_video_merger.core.ffmpeg_runner import run_ffmpeg, ensure_output_dir, get_ffmpeg_path


def parse_time(time_str: str) -> float:
    """
    解析时间字符串为秒数

    支持格式：
    - HH:MM:SS（如 01:30:00）
    - MM:SS（如 90:00）
    - 纯数字（秒数，如 5400）
    """
    time_str = time_str.strip()

    # 纯数字
    if re.match(r"^\d+(\.\d+)?$", time_str):
        return float(time_str)

    # HH:MM:SS 或 MM:SS
    parts = time_str.split(":")
    if len(parts) == 3:
        h, m, s = parts
        return int(h) * 3600 + int(m) * 60 + float(s)
    elif len(parts) == 2:
        m, s = parts
        return int(m) * 60 + float(s)

    raise ValueError(f"无法解析时间格式: {time_str}")


def trim_video(
    input_file: str,
    output_path: str,
    start_time: str = "00:00:00",
    end_time: Optional[str] = None,
    duration: Optional[float] = None,
    mode: str = "copy",
    progress_callback: Optional[Callable] = None,
) -> tuple[bool, Optional[str]]:
    """
    裁剪视频片段

    Args:
        input_file: 输入文件路径
        output_path: 输出文件路径
        start_time: 开始时间（HH:MM:SS 或秒数）
        end_time: 结束时间（与 duration 二选一）
        duration: 持续时长秒数（与 end_time 二选一）
        mode: "copy"（快速，关键帧对齐）或 "recode"（精确，帧级）
        progress_callback: 进度回调

    Returns:
        (成功标志, 错误信息)
    """
    err = ensure_output_dir(output_path)
    if err:
        return False, err

    try:
        start_sec = parse_time(start_time)
    except ValueError as e:
        return False, str(e)

    cmd = [get_ffmpeg_path()]

    # -ss 放在 -i 前面实现快速 seek
    cmd.extend(["-ss", str(start_sec)])
    cmd.extend(["-i", input_file])

    if end_time:
        try:
            end_sec = parse_time(end_time)
            cmd.extend(["-to", str(end_sec)])
        except ValueError as e:
            return False, str(e)
    elif duration:
        cmd.extend(["-t", str(duration)])

    if mode == "copy":
        cmd.extend(["-c", "copy"])
    else:
        cmd.extend(["-c:v", "libx264", "-c:a", "aac"])

    cmd.extend(["-y", output_path])

    if progress_callback:
        progress_callback(f"正在裁剪: {os.path.basename(output_path)}")

    return run_ffmpeg(cmd, output_path, progress_callback, "裁剪")
