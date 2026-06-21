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
    shortest: bool = False,
    audio_recode: bool = False,
    audio_codec: str = "aac",
    audio_bitrate: str = "192k",
) -> list[str]:
    """构建 ffmpeg 合并命令"""
    # 音频编码名称到 FFmpeg 编码器的映射
    codec_map = {
        "aac": "aac",
        "mp3": "libmp3lame",
        "ac3": "ac3",
        "flac": "flac",
    }

    cmd = [get_ffmpeg_path()]

    if video_file:
        cmd.extend(["-i", video_file])
    if audio_file:
        cmd.extend(["-i", audio_file])

    if audio_recode:
        # Fallback 容错模式：复制视频流，重编码音频流
        ffmpeg_codec = codec_map.get(audio_codec, "aac")
        cmd.extend(["-c:v", "copy", "-c:a", ffmpeg_codec])
        # FLAC 为无损编码，无需指定码率；auto 跟随原音频码率
        if audio_codec != "flac" and audio_bitrate and audio_bitrate != "auto":
            cmd.extend(["-b:a", audio_bitrate])
    else:
        # 默认极致流复制
        cmd.extend(["-c", "copy"])

    if video_file and audio_file:
        cmd.extend(["-map", "0:v:0", "-map", "1:a:0"])
        if shortest:
            cmd.extend(["-shortest"])
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
    shortest: bool = False,
    progress_callback: Optional[Callable[[str], None]] = None,
    process_callback=None,
    audio_codec: str = "aac",
    audio_bitrate: str = "192k",
) -> tuple[bool, Optional[str]]:
    """执行单个合并任务"""
    err = ensure_output_dir(output_path)
    if err:
        return False, err

    cmd = build_ffmpeg_command(video_file, audio_file, output_path, shortest=shortest, audio_recode=False)

    if progress_callback:
        progress_callback(f"正在合并: {os.path.basename(output_path)}")

    success, err_msg = run_ffmpeg(cmd, output_path, progress_callback, "合并", process_callback)

    # 智能无损自救 (Fallback): 如果因为容器不兼容导致 copy 报错，触发降级转码
    if not success:
        logger.warning(f"合并流复制失败，触发音频重编码降级重试: {output_path}")
        if progress_callback:
            progress_callback(f"流复制失败，正在进行兼容模式重试: {os.path.basename(output_path)}")
        cmd_fallback = build_ffmpeg_command(
            video_file, audio_file, output_path,
            shortest=shortest, audio_recode=True,
            audio_codec=audio_codec, audio_bitrate=audio_bitrate,
        )
        success, err_msg = run_ffmpeg(cmd_fallback, output_path, progress_callback, "合并(降级)", process_callback)

    return success, err_msg
