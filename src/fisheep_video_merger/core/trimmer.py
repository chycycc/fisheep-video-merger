"""
视频裁剪模块
按起止时间截取视频片段
"""

import os
import re
from typing import Callable, Optional

from fisheep_video_merger.core.ffmpeg_runner import run_ffmpeg, ensure_output_dir, get_ffmpeg_path, get_hw_encoder


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
    accurate_mode: bool = False,
    keep_audio: bool = True,
    keep_video: bool = True,
    progress_callback: Optional[Callable] = None,
) -> tuple[bool, Optional[str]]:
    """裁剪视频片段（极速关键帧 vs 逐帧精准）"""
    err = ensure_output_dir(output_path)
    if err:
        return False, err

    try:
        start_sec = parse_time(start_time)
    except ValueError as e:
        return False, str(e)

    cmd = [get_ffmpeg_path()]

    # 极速模式：-ss 在前（Input seek），仅限关键帧，有秒级误差
    if not accurate_mode:
        cmd.extend(["-ss", str(start_sec)])

    cmd.extend(["-i", input_file])

    # 精准模式：-ss 在后（Output seek），必须搭配重编码，零误差
    if accurate_mode:
        cmd.extend(["-ss", str(start_sec)])

    if end_time:
        try:
            end_sec = parse_time(end_time)
            # 在 output seek 模式下，-to 是相对于 -ss 的。
            # 为了确保绝对时间点正确，统一改用 -t (duration)
            trim_duration = end_sec - start_sec
            if trim_duration > 0:
                cmd.extend(["-t", str(trim_duration)])
        except ValueError as e:
            return False, str(e)
    elif duration:
        cmd.extend(["-t", str(duration)])

    if not accurate_mode:
        cmd.extend(["-c", "copy"])
    else:
        hw_encoder = get_hw_encoder()
        video_codec = hw_encoder if hw_encoder else "libx264"
        cmd.extend(["-c:v", video_codec, "-c:a", "aac"])

    # 音视频流控制：去除音频或视频
    if not keep_audio:
        cmd.extend(["-an"])
    if not keep_video:
        cmd.extend(["-vn"])

    cmd.extend(["-y", output_path])

    if progress_callback:
        mode_str = "精准" if accurate_mode else "极速"
        progress_callback(f"正在{mode_str}裁剪: {os.path.basename(output_path)}")

    return run_ffmpeg(cmd, output_path, progress_callback, "裁剪")
