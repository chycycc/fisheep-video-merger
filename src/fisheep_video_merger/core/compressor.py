"""
视频压缩模块
降低码率/分辨率减小文件体积
"""

import os
from typing import Callable, Optional

from fisheep_video_merger.core.ffmpeg_runner import run_ffmpeg, ensure_output_dir, get_ffmpeg_path, get_hw_encoder

# 压缩预设：(CRF值, FFmpeg预设速度)
_PRESETS = {
    "fast":     (28, "ultrafast"),   # 快速：文件较大，速度最快
    "balanced": (23, "medium"),       # 均衡：推荐
    "quality":  (20, "slow"),         # 高质量：文件最小，速度最慢
}

# 分辨率缩放
_RESOLUTION_SCALE = {
    "original": None,
    "1080p": "1920:-2",
    "720p": "1280:-2",
    "480p": "854:-2",
}


def compress_video(
    input_file: str,
    output_path: str,
    preset: str = "balanced",
    resolution: str = "original",
    progress_callback: Optional[Callable] = None,
) -> tuple[bool, Optional[str]]:
    """
    压缩视频文件

    Args:
        input_file: 输入文件路径
        output_path: 输出文件路径
        preset: 压缩预设（fast/balanced/quality）
        resolution: 分辨率缩放（original/1080p/720p/480p）
        progress_callback: 进度回调

    Returns:
        (成功标志, 错误信息)
    """
    err = ensure_output_dir(output_path)
    if err:
        return False, err

    crf, ffmpeg_preset = _PRESETS.get(preset, _PRESETS["balanced"])
    scale = _RESOLUTION_SCALE.get(resolution)

    # 优先使用硬件加速编码器
    hw_encoder = get_hw_encoder()
    if hw_encoder:
        cmd = [
            get_ffmpeg_path(),
            "-i", input_file,
            "-c:v", hw_encoder,
            "-cq", str(crf),
            "-c:a", "aac",
            "-b:a", "128k",
        ]
    else:
        cmd = [
            get_ffmpeg_path(),
            "-i", input_file,
            "-c:v", "libx264",
            "-preset", ffmpeg_preset,
            "-crf", str(crf),
            "-c:a", "aac",
            "-b:a", "128k",
        ]

    if scale:
        cmd.extend(["-vf", f"scale={scale}"])

    cmd.extend(["-y", output_path])

    if progress_callback:
        progress_callback(f"正在压缩: {os.path.basename(output_path)}")

    return run_ffmpeg(cmd, output_path, progress_callback, "压缩")
