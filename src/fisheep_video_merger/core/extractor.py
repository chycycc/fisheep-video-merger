"""
音频提取模块
从视频文件中提取音轨
"""

import os
from typing import Callable, Optional

from fisheep_video_merger.core.ffmpeg_runner import run_ffmpeg, ensure_output_dir, get_ffmpeg_path
from fisheep_video_merger.utils.logger import get_logger

logger = get_logger()


# 格式到编码器的映射
_FORMAT_CODEC = {
    "mp3": "libmp3lame",
    "aac": "aac",
    "flac": "flac",
    "wav": "pcm_s16le",
}

# 支持码率设置的格式
_BITRATE_FORMATS = {"mp3"}


def extract_audio(
    input_file: str,
    output_path: str,
    audio_format: str = "mp3",
    bitrate: str = "192k",
    progress_callback: Optional[Callable] = None,
) -> tuple[bool, Optional[str]]:
    """
    从视频中提取音频

    Args:
        input_file: 输入文件路径
        output_path: 输出文件路径
        audio_format: 输出格式（mp3/aac/flac/wav）
        bitrate: 音频码率（仅 mp3 有效）
        progress_callback: 进度回调

    Returns:
        (成功标志, 错误信息)
    """
    err = ensure_output_dir(output_path)
    if err:
        return False, err

    cmd = [get_ffmpeg_path(), "-i", input_file, "-vn"]

    # AAC 格式：直接输出到 M4A 容器（MP4 容器记录精确时长，ADTS 不准）
    if audio_format == "aac":
        cmd.extend(["-c:a", "aac", "-b:a", bitrate, "-f", "mp4"])
    else:
        codec = _FORMAT_CODEC.get(audio_format, "aac")
        cmd.extend(["-c:a", codec])
        if audio_format in _BITRATE_FORMATS:
            cmd.extend(["-b:a", bitrate])

    cmd.extend(["-y", output_path])

    if progress_callback:
        progress_callback(f"正在提取音频: {os.path.basename(output_path)}")

    return run_ffmpeg(cmd, output_path, progress_callback, "提取")
