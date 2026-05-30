"""
合并引擎模块
负责调用 ffmpeg 执行合并操作
"""

import os
from typing import Callable, Optional

from fisheep_video_merger.utils.logger import get_logger
from fisheep_video_merger.core.ffmpeg_runner import get_ffmpeg_path, run_ffmpeg, ensure_output_dir

logger = get_logger()


def build_ffmpeg_command(
    video_file: str,
    audio_file: str,
    output_path: str,
) -> list[str]:
    """
    构建 ffmpeg 合并命令

    使用流复制模式，保留原始质量。

    Args:
        video_file: 视频文件路径
        audio_file: 音频文件路径
        output_path: 输出文件路径

    Returns:
        ffmpeg 命令参数列表
    """
    cmd = [get_ffmpeg_path()]

    if video_file:
        cmd.extend(["-i", video_file])
    if audio_file:
        cmd.extend(["-i", audio_file])

    cmd.extend(["-c", "copy"])

    if video_file and audio_file:
        cmd.extend(["-map", "0:v:0", "-map", "1:a:0"])
    elif video_file:
        cmd.extend(["-map", "0:v:0"])
    elif audio_file:
        cmd.extend(["-map", "0:a:0"])

    # 保留元数据
    cmd.extend(["-map_metadata", "0"])
    
    # MP4/M4A 流媒体加速
    if output_path.lower().endswith((".mp4", ".m4a")):
        cmd.extend(["-movflags", "+faststart"])

    cmd.extend(["-y", output_path])
    return cmd


def merge_single(
    video_file: str,
    audio_file: str,
    output_path: str,
    progress_callback: Optional[Callable[[str], None]] = None,
    process_callback=None,
) -> tuple[bool, Optional[str]]:
    """
    执行单个合并任务

    Args:
        video_file: 视频文件路径
        audio_file: 音频文件路径
        output_path: 输出文件路径
        progress_callback: 进度回调

    Returns:
        (成功标志, 错误信息)
    """
    err = ensure_output_dir(output_path)
    if err:
        return False, err

    cmd = build_ffmpeg_command(video_file, audio_file, output_path)

    if progress_callback:
        progress_callback(f"正在准备合并: {os.path.basename(output_path)}")

    return run_ffmpeg(cmd, output_path, progress_callback, "合并", process_callback)
