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
    "opus": "libopus",
    "ogg": "libvorbis",
    "m4a": "aac",
    "wma": "wmav2",
}

# 支持码率设置的格式
_BITRATE_FORMATS = {"mp3", "aac", "m4a", "opus", "ogg", "wma"}

# 源编码到目标格式的流复制兼容映射
_STREAM_COPY_COMPAT = {
    "mp3": {"mp3"},
    "aac": {"aac"},
    "flac": {"flac"},
    "wav": {"wav", "pcm_s16le", "pcm_s24le", "pcm_f32le"},
    "opus": {"opus"},
    "ogg": {"vorbis"},
    "m4a": {"aac"},
    "wma": {"wmav2"},
}


def _can_use_stream_copy(input_file: str, audio_format: str,
                         channels: str, sample_rate: str, volume: float) -> bool:
    """判断是否可用流复制（源编码匹配 + 无滤镜修改）"""
    # 有滤镜/声道/采样率修改时必须重编码
    volume = volume if volume is not None else 1.0
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
    use_loudnorm: bool = False,
    progress_callback: Optional[Callable] = None,
) -> tuple[bool, Optional[str]]:
    """
    从视频中提取音频

    Args:
        input_file: 输入文件路径
        output_path: 输出文件路径
        audio_format: 输出格式（mp3/aac/flac/wav/opus/ogg/m4a/wma）
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

    # 启用 loudnorm 时绝对不能使用流复制
    can_stream_copy = not use_loudnorm and _can_use_stream_copy(input_file, audio_format, channels, sample_rate, volume)

    def build_cmd(stream_copy: bool) -> list[str]:
        cmd = [get_ffmpeg_path(), "-i", input_file, "-vn"]
        
        if stream_copy:
            cmd.extend(["-c:a", "copy"])
            if audio_format in ("aac", "m4a"):
                cmd.extend(["-f", "mp4"])
            elif audio_format == "opus":
                cmd.extend(["-f", "ogg"])
            elif audio_format == "ogg":
                cmd.extend(["-f", "ogg"])
        else:
            if channels == "mono":
                cmd.extend(["-ac", "1"])
            elif channels == "stereo":
                cmd.extend(["-ac", "2"])

            if sample_rate != "original":
                cmd.extend(["-ar", sample_rate])

            filters = []
            if use_loudnorm:
                filters.append("loudnorm=I=-16:TP=-1.5:LRA=11")
            elif volume is not None and volume != 1.0 and volume > 0:
                filters.append(f"volume={volume}")
            if filters:
                cmd.extend(["-af", ",".join(filters)])

            if audio_format in ("aac", "m4a"):
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
                    elif bitrate_mode == "vbr" and audio_format == "opus":
                        # Opus VBR 通过 -b:a 设目标码率，libopus 默认 VBR
                        cmd.extend(["-b:a", bitrate, "-vbr", "on"])
                    else:
                        cmd.extend(["-b:a", bitrate])
                # 指定容器格式
                if audio_format == "opus":
                    cmd.extend(["-f", "ogg"])
                elif audio_format == "ogg":
                    cmd.extend(["-f", "ogg"])
                        
        # 继承元数据
        cmd.extend(["-map_metadata", "0"])
        
        # MP4/M4A 流媒体加速
        if output_path.lower().endswith((".mp4", ".m4a")):
            cmd.extend(["-movflags", "+faststart"])

        cmd.extend(["-y", output_path])
        return cmd

    cmd = build_cmd(can_stream_copy)
    if can_stream_copy:
        logger.info(f"音频流复制模式（跳过重编码）: {os.path.basename(input_file)}")

    if progress_callback:
        progress_callback(f"正在提取音频: {os.path.basename(output_path)}")

    success, err = run_ffmpeg(cmd, output_path, progress_callback, "提取")
    
    # 智能无损自救 (Fallback)
    if not success and can_stream_copy:
        logger.warning(f"流复制失败，触发重编码降级重试: {input_file}")
        if progress_callback:
            progress_callback(f"流复制失败，正在降级重试: {os.path.basename(output_path)}")
        cmd_fallback = build_cmd(stream_copy=False)
        success, err = run_ffmpeg(cmd_fallback, output_path, progress_callback, "提取(降级)")
        
    return success, err
