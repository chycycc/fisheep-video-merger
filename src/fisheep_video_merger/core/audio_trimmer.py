"""
音频裁剪模块
按起止时间截取音频片段，支持极速模式（流复制）和精准模式（重编码）
"""

import os
from typing import Callable, Optional

from fisheep_video_merger.core.ffmpeg_runner import run_ffmpeg, ensure_output_dir, get_ffmpeg_path
from fisheep_video_merger.core.trimmer import parse_time
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


def trim_audio(
    input_file: str,
    output_path: str,
    start_time: str = "00:00:00",
    end_time: Optional[str] = None,
    accurate_mode: bool = False,
    output_format: str = "",
    bitrate: str = "192k",
    progress_callback: Optional[Callable] = None,
) -> tuple[bool, Optional[str]]:
    """
    裁剪音频片段

    Args:
        input_file: 输入文件路径
        output_path: 输出文件路径
        start_time: 开始时间（支持 HH:MM:SS / MM:SS / 纯秒数）
        end_time: 结束时间（可选）
        accurate_mode: 是否精准模式（True=重编码，False=流复制）
        output_format: 输出格式（为空时使用源文件格式）
        bitrate: 音频码率（默认 192k）
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

    # 极速模式：-ss 在前（Input seek），配合 -c copy 流复制
    if not accurate_mode:
        cmd.extend(["-ss", str(start_sec)])

    cmd.extend(["-i", input_file])

    # 精准模式：-ss 在后（Output seek），配合重编码实现零误差
    if accurate_mode:
        cmd.extend(["-ss", str(start_sec)])

    # 计算裁剪时长
    if end_time:
        try:
            end_sec = parse_time(end_time)
            trim_duration = end_sec - start_sec
            if trim_duration > 0:
                cmd.extend(["-t", str(trim_duration)])
        except ValueError as e:
            return False, str(e)

    # 编码设置
    if not accurate_mode:
        # 极速模式：流复制
        cmd.extend(["-c", "copy"])
    else:
        # 精准模式：根据输出格式选择编码器
        if output_format:
            fmt = output_format.lower()
        else:
            # 从源文件扩展名推断格式
            fmt = os.path.splitext(input_file)[1].lstrip(".").lower()

        codec = _FORMAT_CODEC.get(fmt, "aac")
        cmd.extend(["-c:a", codec])

        # 仅对支持码率的格式设置码率
        if fmt in ("mp3", "aac", "m4a", "opus", "ogg", "wma"):
            cmd.extend(["-b:a", bitrate])

    # 根据输出格式设置容器格式
    if output_format:
        fmt = output_format.lower()
    else:
        fmt = os.path.splitext(input_file)[1].lstrip(".").lower()

    if fmt in ("aac", "m4a"):
        cmd.extend(["-f", "mp4"])
    elif fmt in ("opus", "ogg"):
        cmd.extend(["-f", "ogg"])

    # MP4/M4A 输出加流媒体加速标记
    if output_path.lower().endswith((".mp4", ".m4a")):
        cmd.extend(["-movflags", "+faststart"])

    # 保留元数据
    cmd.extend(["-map_metadata", "0"])

    cmd.extend(["-y", output_path])

    mode_str = "精准" if accurate_mode else "极速"
    logger.info(f"音频裁剪: {os.path.basename(input_file)} [{mode_str}] -> {os.path.basename(output_path)}")

    if progress_callback:
        progress_callback(f"正在{mode_str}裁剪: {os.path.basename(output_path)}")

    return run_ffmpeg(cmd, output_path, progress_callback, "裁剪")
