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
    crf: int = 23,
    preset: str = "medium",
    scale: str = "original",
    fps: str = "original",
    progress_callback: Optional[Callable] = None,
) -> tuple[bool, Optional[str]]:
    """
    转换单个视频文件格式
    """
    err = ensure_output_dir(output_path)
    if err:
        return False, err

    cmd = [get_ffmpeg_path(), "-i", input_file]

    if fps != "original" and fps:
        cmd.extend(["-r", fps])

    if scale != "original" and scale:
        scale_map = {"1080p": "1920:-2", "720p": "1280:-2", "480p": "854:-2"}
        scale_val = scale_map.get(scale, scale)
        cmd.extend(["-vf", f"scale={scale_val}"])

    if mode == "copy":
        cmd.extend(["-c", "copy"])
    else:
        # H.264 or HEVC (H.265)
        vcodec = "libx265" if mode == "hevc" else "libx264"
        hw_encoder = get_hw_encoder()
        
        # 仅当使用 h264 且存在硬件加速时使用硬编（暂不引入复杂的 h265 硬编检测）
        if mode == "h264" and hw_encoder:
            vcodec = hw_encoder

        cmd.extend([
            "-c:v", vcodec,
            "-preset", preset,
            "-crf", str(crf),
            "-c:a", "aac",
            "-b:a", "192k"
        ])

    cmd.extend(["-y", output_path])

    if progress_callback:
        progress_callback(f"正在转换: {os.path.basename(output_path)}")

    return run_ffmpeg(cmd, output_path, progress_callback, "转换")
