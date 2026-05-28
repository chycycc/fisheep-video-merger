"""
音频提取模块
从视频文件中提取音轨，支持声道/采样率/音量/CBR-VBR 等高级设置
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
_BITRATE_FORMATS = {"mp3", "aac"}

# 源编码到目标格式的流复制兼容映射
_STREAM_COPY_COMPAT = {
    "mp3": {"mp3"},
    "aac": {"aac"},
    "flac": {"flac"},
    "wav": {"wav", "pcm_s16le", "pcm_s24le", "pcm_f32le"},
}


def _can_use_stream_copy(input_file: str, audio_format: str,
                         channels: str, sample_rate: str, volume: float) -> bool:
    """判断是否可用流复制（源编码匹配 + 无滤镜修改）"""
    # 有滤镜/声道/采样率修改时必须重编码
    if channels != "original" or sample_rate != "original" or (volume != 1.0 and volume > 0):
        return False
    # 检测源音频编码
    try:
        from fisheep_video_merger.utils.ffprobe import get_video_detail
        detail = get_video_detail(input_file)
        src_codec = detail.audio_codec.lower() if detail.audio_codec else ""
        compat = _STREAM_COPY_COMPAT.get(audio_format, set())
        return src_codec in compat
    except Exception:
        return False


# 编码质量预设
PRESETS = {
    "high":     {"bitrate": "320k", "sample_rate": "48000", "channels": "stereo"},
    "medium":   {"bitrate": "192k", "sample_rate": "44100", "channels": "stereo"},
    "low":      {"bitrate": "128k", "sample_rate": "22050", "channels": "mono"},
}


def extract_audio(
    input_file: str,
    output_path: str,
    audio_format: str = "mp3",
    bitrate: str = "192k",
    channels: str = "original",
    sample_rate: str = "original",
    volume: float = 1.0,
    bitrate_mode: str = "cbr",
    progress_callback: Optional[Callable] = None,
) -> tuple[bool, Optional[str]]:
    """
    从视频中提取音频

    Args:
        input_file: 输入文件路径
        output_path: 输出文件路径
        audio_format: 输出格式（mp3/aac/flac/wav）
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

    # 检测源音频编码，判断是否可用流复制（10-100x 快于重编码）
    can_stream_copy = _can_use_stream_copy(input_file, audio_format, channels, sample_rate, volume)

    cmd = [get_ffmpeg_path(), "-i", input_file, "-vn"]

    if can_stream_copy:
        # 流复制模式：不重编码，直接复制音频流
        cmd.extend(["-c:a", "copy"])
        if audio_format == "aac":
            cmd.extend(["-f", "mp4"])
        logger.info(f"音频流复制模式（跳过重编码）: {os.path.basename(input_file)}")
    else:
        # 重编码模式
        # 声道设置
        if channels == "mono":
            cmd.extend(["-ac", "1"])
        elif channels == "stereo":
            cmd.extend(["-ac", "2"])

        # 采样率设置
        if sample_rate != "original":
            cmd.extend(["-ar", sample_rate])

        # 音频滤镜（音量调节）
        filters = []
        if volume != 1.0 and volume > 0:
            filters.append(f"volume={volume}")
        if filters:
            cmd.extend(["-af", ",".join(filters)])

        # 编码器和码率
        if audio_format == "aac":
            cmd.extend(["-c:a", "aac"])
            if bitrate_mode == "vbr":
                cmd.extend(["-q:a", "2"])
            else:
                cmd.extend(["-b:a", bitrate])
            cmd.extend(["-f", "mp4"])
        else:
            codec = _FORMAT_CODEC.get(audio_format, "aac")
            cmd.extend(["-c:a", codec])
            if audio_format in _BITRATE_FORMATS:
                if bitrate_mode == "vbr" and audio_format == "mp3":
                    cmd.extend(["-q:a", "2"])
                else:
                    cmd.extend(["-b:a", bitrate])

    cmd.extend(["-y", output_path])

    if progress_callback:
        progress_callback(f"正在提取音频: {os.path.basename(output_path)}")

    return run_ffmpeg(cmd, output_path, progress_callback, "提取")
