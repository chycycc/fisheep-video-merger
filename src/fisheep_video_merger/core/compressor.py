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
    "4k": "3840:-2",
    "1080p": "1920:-2",
    "720p": "1280:-2",
    "480p": "854:-2",
    "360p": "640:-2",
}


def compress_video(
    input_file: str,
    output_path: str,
    preset: str = "balanced",
    resolution: str = "original",
    target_size_mb: Optional[float] = None,
    target_bitrate: Optional[str] = None,
    custom_crf: Optional[int] = None,
    audio_codec: str = "aac",
    audio_bitrate: str = "128k",
    audio_copy: bool = True,
    progress_callback: Optional[Callable] = None,
) -> tuple[bool, Optional[str]]:
    """压缩视频文件（支持快速 CRF 与精准 Two-Pass）"""
    err = ensure_output_dir(output_path)
    if err:
        return False, err

    crf, ffmpeg_preset = _PRESETS.get(preset, _PRESETS["balanced"])
    # 自定义 CRF 覆盖预设值
    if custom_crf is not None:
        crf = custom_crf
    scale = _RESOLUTION_SCALE.get(resolution)

    # 构建基础参数
    base_cmd = [get_ffmpeg_path(), "-i", input_file]
    if scale:
        base_cmd.extend(["-vf", f"scale={scale}"])

    # 确定音频参数
    if audio_copy:
        audio_args = ["-c:a", "copy"]
    else:
        audio_args = ["-c:a", audio_codec, "-b:a", audio_bitrate]
    
    hw_encoder = get_hw_encoder()

    if target_size_mb or target_bitrate:
        # 启用精准 Two-Pass 压缩
        try:
            from fisheep_video_merger.utils.ffprobe import get_video_detail
            detail = get_video_detail(input_file)
            if not detail or detail.duration <= 0:
                return False, "无法获取视频时长，Two-Pass 失败"

            if target_bitrate:
                # 按目标码率压缩：直接使用用户指定的码率
                target_video_bitrate = int(target_bitrate.replace("k", "").replace("K", ""))
            else:
                # 按目标文件大小压缩：计算目标视频码率 (kbps)
                target_total_bitrate = (target_size_mb * 8192) / detail.duration
                ab = int(audio_bitrate.replace("k", "").replace("K", "")) if not audio_copy else 192
                target_video_bitrate = max(100, int(target_total_bitrate - ab))
            
            passlog_path = output_path + "_passlog"
            
            # Pass 1
            cmd_pass1 = base_cmd.copy()
            cmd_pass1.extend([
                "-c:v", "libx264", # Pass 1 通常用软编保证统计准确
                "-b:v", f"{target_video_bitrate}k",
                "-preset", ffmpeg_preset,
                "-pass", "1",
                "-passlogfile", passlog_path,
                "-an", "-f", "null",
                "NUL" if os.name == 'nt' else "/dev/null"
            ])
            
            if progress_callback:
                progress_callback(f"精准压缩 (1/2): 分析视频源中...")
            
            success, err_msg = run_ffmpeg(cmd_pass1, output_path, progress_callback, "压缩(Pass-1)")
            if not success:
                return False, err_msg
                
            # Pass 2
            cmd_pass2 = base_cmd.copy()
            cmd_pass2.extend([
                "-c:v", "libx264",
                "-b:v", f"{target_video_bitrate}k",
                "-preset", ffmpeg_preset,
                "-pass", "2",
                "-passlogfile", passlog_path,
            ])
            cmd_pass2.extend(audio_args)
            cmd_pass2.extend(["-y", output_path])
            
            if progress_callback:
                progress_callback(f"精准压缩 (2/2): 正在生成文件...")
                
            success, err_msg = run_ffmpeg(cmd_pass2, output_path, progress_callback, "压缩(Pass-2)")
            
            # 清理 log
            for ext in ["-0.log", "-0.log.mbtree"]:
                if os.path.exists(passlog_path + ext):
                    os.remove(passlog_path + ext)
                    
            return success, err_msg

        except Exception as e:
            return False, f"Two-Pass 执行失败: {e}"
            
    else:
        # 快速 CRF 压缩
        cmd = base_cmd.copy()
        if hw_encoder:
            cmd.extend(["-c:v", hw_encoder, "-cq", str(crf)])
        else:
            cmd.extend(["-c:v", "libx264", "-preset", ffmpeg_preset, "-crf", str(crf)])
            
        cmd.extend(audio_args)
        cmd.extend(["-y", output_path])

        if progress_callback:
            progress_callback(f"正在压缩: {os.path.basename(output_path)}")

        return run_ffmpeg(cmd, output_path, progress_callback, "压缩")
