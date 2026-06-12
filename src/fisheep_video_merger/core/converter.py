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
        # 编码器映射：mode → vcodec
        codec_map = {
            "recode": "libx264",
            "h264": "libx264",
            "hevc": "libx265",
            "av1": "libsvtav1",
            "vp9": "libvpx-vp9",
        }
        vcodec = codec_map.get(mode, "libx264")
        hw_encoder = get_hw_encoder()

        # 仅当使用 h264 且存在硬件加速时使用硬编（暂不引入复杂的 h265 硬编检测）
        if mode in ("h264", "recode") and hw_encoder:
            vcodec = hw_encoder
            # NVENC 预设映射：libx264 预设 -> NVENC 预设
            nvenc_preset_map = {
                "ultrafast": "fast", "superfast": "fast", "veryfast": "fast",
                "faster": "fast", "fast": "fast", "medium": "medium",
                "slow": "slow", "slower": "slow", "veryslow": "slow",
            }
            preset = nvenc_preset_map.get(preset, "medium")

        # NVENC 用 -cq 代替 -crf
        crf_flag = "-cq" if (mode == "h264" and hw_encoder) else "-crf"

        if mode == "vp9":
            # VP9 不支持 -preset，使用 -deadline 和 -cpu-used 替代
            cmd.extend([
                "-c:v", vcodec,
                "-deadline", "good",
                "-cpu-used", "2",
                "-crf", str(crf),
                "-c:a", "libopus",
                "-b:a", "192k"
            ])
        else:
            cmd.extend([
                "-c:v", vcodec,
                "-preset", preset,
                crf_flag, str(crf),
                "-c:a", "aac",
                "-b:a", "192k"
            ])

    cmd.extend(["-y", output_path])

    if progress_callback:
        progress_callback(f"正在转换: {os.path.basename(output_path)}")

    return run_ffmpeg(cmd, output_path, progress_callback, "转换")
