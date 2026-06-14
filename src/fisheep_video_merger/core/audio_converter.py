"""
音频转换模块
将音频文件转换为其他音频格式，支持码率/声道/采样率/音量等高级设置
"""

import os
from typing import Callable, Optional

from fisheep_video_merger.core.ffmpeg_runner import run_ffmpeg, ensure_output_dir, get_ffmpeg_path
from fisheep_video_merger.utils.logger import get_logger

logger = get_logger()


# 格式到编码器的映射
from fisheep_video_merger.core.constants import FORMAT_AUDIO_CODEC as _FORMAT_CODEC

# 支持码率设置的格式
_BITRATE_FORMATS = {"mp3", "aac", "m4a", "opus", "ogg", "wma"}


def convert_audio(
    input_file: str,
    output_path: str,
    output_format: str = "mp3",
    bitrate: str = "192k",
    channels: str = "original",
    sample_rate: str = "original",
    volume: float = 1.0,
    bitrate_mode: str = "cbr",
    progress_callback: Optional[Callable] = None,
) -> tuple[bool, Optional[str]]:
    """
    将音频文件转换为指定格式

    Args:
        input_file: 输入文件路径
        output_path: 输出文件路径
        output_format: 输出格式（mp3/aac/flac/wav/opus/ogg/m4a/wma）
        bitrate: 音频码率（如 "192k"）
        channels: 声道（"original"/"stereo"/"mono"）
        sample_rate: 采样率（"original"/"44100"/"48000" 等）
        volume: 音量增益（0.5-2.0，1.0 为原始音量）
        bitrate_mode: 码率模式（"cbr"/"vbr"）
        progress_callback: 进度回调

    Returns:
        (成功标志, 错误信息)
    """
    err = ensure_output_dir(output_path)
    if err:
        return False, err

    def build_cmd() -> list[str]:
        cmd = [get_ffmpeg_path(), "-i", input_file]
        # 注意：不需要 -vn，因为输入本身就是音频

        # 声道设置
        if channels == "mono":
            cmd.extend(["-ac", "1"])
        elif channels == "stereo":
            cmd.extend(["-ac", "2"])

        # 采样率设置
        if sample_rate != "original":
            cmd.extend(["-ar", sample_rate])

        # 音量滤镜
        filters = []
        if volume != 1.0 and volume > 0:
            filters.append(f"volume={volume}")
        if filters:
            cmd.extend(["-af", ",".join(filters)])

        # 编码器与码率
        if output_format in ("aac", "m4a"):
            cmd.extend(["-c:a", "aac"])
            if bitrate_mode == "vbr":
                cmd.extend(["-q:a", "2"])
            else:
                cmd.extend(["-b:a", bitrate])
            cmd.extend(["-f", "mp4"])
        else:
            codec = _FORMAT_CODEC.get(output_format, "aac")
            cmd.extend(["-c:a", codec])
            if output_format in _BITRATE_FORMATS:
                if bitrate_mode == "vbr" and output_format == "mp3":
                    cmd.extend(["-q:a", "2"])
                elif bitrate_mode == "vbr" and output_format == "opus":
                    # Opus VBR 通过 -b:a 设目标码率，libopus 默认 VBR
                    cmd.extend(["-b:a", bitrate, "-vbr", "on"])
                else:
                    cmd.extend(["-b:a", bitrate])
            # 指定容器格式
            if output_format == "opus":
                cmd.extend(["-f", "ogg"])
            elif output_format == "ogg":
                cmd.extend(["-f", "ogg"])

        # 继承元数据
        cmd.extend(["-map_metadata", "0"])

        # MP4/M4A 流媒体加速
        if output_path.lower().endswith((".mp4", ".m4a")):
            cmd.extend(["-movflags", "+faststart"])

        cmd.extend(["-y", output_path])
        return cmd

    cmd = build_cmd()
    logger.info(f"音频转换: {os.path.basename(input_file)} -> {output_format}")

    if progress_callback:
        progress_callback(f"正在转换音频: {os.path.basename(output_path)}")

    success, err = run_ffmpeg(cmd, output_path, progress_callback, "转换")

    return success, err
