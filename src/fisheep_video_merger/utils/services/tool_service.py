"""
工具服务
负责视频工具操作（转换、提取、压缩、裁剪、预览）
"""

import os
import json
import base64
import subprocess
from typing import Dict, Optional
from concurrent.futures import ThreadPoolExecutor as TPE

from fisheep_video_merger.core.converter import convert_single
from fisheep_video_merger.core.extractor import extract_audio
from fisheep_video_merger.core.compressor import compress_video
from fisheep_video_merger.core.trimmer import trim_video
from fisheep_video_merger.core.subtitle import (
    adjust_subtitle,
    adjust_subtitle_segments,
    merge_subtitles,
    convert_subtitle,
    split_bilingual,
    extract_from_video,
)
from fisheep_video_merger.utils.ffprobe import get_video_detail, extract_screenshot
from fisheep_video_merger.utils.logger import get_logger

logger = get_logger()


class ToolService:
    """视频工具操作"""

    def __init__(self):
        pass

    def convert_file(self, input_file: str, output_format: str, mode: str,
                     output_dir: str = "", output_name: str = "",
                     progress_callback=None) -> Dict:
        """格式转换"""
        if not os.path.exists(input_file):
            return {"status": "error", "message": "文件不存在"}

        if not output_dir:
            output_dir = os.path.dirname(input_file)
        if output_name:
            name = os.path.splitext(output_name)[0]
        else:
            name = os.path.splitext(os.path.basename(input_file))[0]
        output_path = os.path.join(output_dir, f"{name}.{output_format}")
        output_path = self._resolve_conflict(output_path)

        success, err = convert_single(input_file, output_path, mode, progress_callback)
        return {"status": "success" if success else "error", "output_path": output_path, "message": err}

    def extract_audio_api(self, input_file: str, audio_format: str, bitrate: str,
                          output_dir: str = "", output_name: str = "",
                          channels: str = "original", sample_rate: str = "original",
                          volume: float = 1.0, bitrate_mode: str = "cbr",
                          progress_callback=None) -> Dict:
        """音频提取"""
        if not os.path.exists(input_file):
            return {"status": "error", "message": "文件不存在"}

        if not output_dir:
            output_dir = os.path.dirname(input_file)
        if output_name:
            name = os.path.splitext(output_name)[0]
        else:
            name = os.path.splitext(os.path.basename(input_file))[0]
        ext = "m4a" if audio_format == "aac" else audio_format
        output_path = os.path.join(output_dir, f"{name}.{ext}")
        output_path = self._resolve_conflict(output_path)

        try:
            success, err = extract_audio(
                input_file, output_path, audio_format, bitrate,
                channels=channels, sample_rate=sample_rate,
                volume=volume, bitrate_mode=bitrate_mode,
                progress_callback=progress_callback
            )
            return {"status": "success" if success else "error", "output_path": output_path, "message": err}
        except Exception as e:
            logger.error(f"提取音频异常: {e}")
            return {"status": "error", "message": str(e)}

    def compress_video_api(self, input_file: str, preset: str, resolution: str,
                           output_dir: str = "", output_name: str = "",
                           progress_callback=None) -> Dict:
        """视频压缩"""
        if not os.path.exists(input_file):
            return {"status": "error", "message": "文件不存在"}

        if not output_dir:
            output_dir = os.path.dirname(input_file)
        if output_name:
            name = os.path.splitext(output_name)[0]
        else:
            name = os.path.splitext(os.path.basename(input_file))[0] + "_compressed"
        ext = os.path.splitext(input_file)[1]
        output_path = os.path.join(output_dir, f"{name}{ext}")
        output_path = self._resolve_conflict(output_path)

        success, err = compress_video(input_file, output_path, preset, resolution, progress_callback)
        return {"status": "success" if success else "error", "output_path": output_path, "message": err}

    def trim_video_api(self, input_file: str, start_time: str, end_time: str, mode: str,
                       output_dir: str = "", output_name: str = "",
                       progress_callback=None) -> Dict:
        """视频裁剪"""
        if not os.path.exists(input_file):
            return {"status": "error", "message": "文件不存在"}

        if not output_dir:
            output_dir = os.path.dirname(input_file)
        if output_name:
            name = os.path.splitext(output_name)[0]
        else:
            name = os.path.splitext(os.path.basename(input_file))[0] + "_trimmed"
        ext = os.path.splitext(input_file)[1]
        output_path = os.path.join(output_dir, f"{name}{ext}")
        output_path = self._resolve_conflict(output_path)

        accurate_mode = (mode in ("accurate", "recode"))
        success, err = trim_video(input_file, output_path, start_time, end_time, accurate_mode=accurate_mode, progress_callback=progress_callback)
        return {"status": "success" if success else "error", "output_path": output_path, "message": err}

    # ── 字幕工具 ──────────────────────────────────────────

    def subtitle_adjust_api(self, input_file: str, offset_ms: int,
                            output_dir: str = "", output_name: str = "",
                            progress_callback=None) -> Dict:
        """字幕整体调轴"""
        if not os.path.exists(input_file):
            return {"status": "error", "message": "文件不存在"}

        if not output_dir:
            output_dir = os.path.dirname(input_file)
        if output_name:
            name = os.path.splitext(output_name)[0]
        else:
            name = os.path.splitext(os.path.basename(input_file))[0] + "_adjusted"
        ext = os.path.splitext(input_file)[1]
        output_path = os.path.join(output_dir, f"{name}{ext}")
        output_path = self._resolve_conflict(output_path)

        try:
            success, err = adjust_subtitle(input_file, output_path, offset_ms, progress_callback)
            return {"status": "success" if success else "error", "output_path": output_path, "message": err}
        except Exception as e:
            logger.error(f"字幕调轴异常: {e}")
            return {"status": "error", "message": str(e)}

    def subtitle_adjust_segments_api(self, input_file: str, segments: list,
                                     output_dir: str = "", output_name: str = "",
                                     progress_callback=None) -> Dict:
        """字幕按片段调轴"""
        if not os.path.exists(input_file):
            return {"status": "error", "message": "文件不存在"}

        if not output_dir:
            output_dir = os.path.dirname(input_file)
        if output_name:
            name = os.path.splitext(output_name)[0]
        else:
            name = os.path.splitext(os.path.basename(input_file))[0] + "_adjusted"
        ext = os.path.splitext(input_file)[1]
        output_path = os.path.join(output_dir, f"{name}{ext}")
        output_path = self._resolve_conflict(output_path)

        try:
            success, err = adjust_subtitle_segments(input_file, output_path, segments, progress_callback)
            return {"status": "success" if success else "error", "output_path": output_path, "message": err}
        except Exception as e:
            logger.error(f"字幕按片段调轴异常: {e}")
            return {"status": "error", "message": str(e)}

    def subtitle_merge_api(self, file_a: str, file_b: str,
                           output_dir: str = "", output_name: str = "",
                           layout: str = "top_bottom",
                           progress_callback=None) -> Dict:
        """字幕合并（双语）"""
        if not os.path.exists(file_a):
            return {"status": "error", "message": f"文件不存在: {file_a}"}
        if not os.path.exists(file_b):
            return {"status": "error", "message": f"文件不存在: {file_b}"}

        if not output_dir:
            output_dir = os.path.dirname(file_a)
        if output_name:
            name = os.path.splitext(output_name)[0]
        else:
            name_a = os.path.splitext(os.path.basename(file_a))[0]
            name_b = os.path.splitext(os.path.basename(file_b))[0]
            name = f"{name_a}+{name_b}_merged"
        ext = os.path.splitext(file_a)[1]
        output_path = os.path.join(output_dir, f"{name}{ext}")
        output_path = self._resolve_conflict(output_path)

        try:
            success, err = merge_subtitles(file_a, file_b, output_path, layout, progress_callback)
            return {"status": "success" if success else "error", "output_path": output_path, "message": err}
        except Exception as e:
            logger.error(f"字幕合并异常: {e}")
            return {"status": "error", "message": str(e)}

    def subtitle_convert_api(self, input_file: str, target_format: str,
                             output_dir: str = "", output_name: str = "",
                             progress_callback=None) -> Dict:
        """字幕格式转换"""
        if not os.path.exists(input_file):
            return {"status": "error", "message": "文件不存在"}

        fmt = target_format.lower().lstrip(".")
        if not output_dir:
            output_dir = os.path.dirname(input_file)
        if output_name:
            name = os.path.splitext(output_name)[0]
        else:
            name = os.path.splitext(os.path.basename(input_file))[0]
        output_path = os.path.join(output_dir, f"{name}.{fmt}")
        output_path = self._resolve_conflict(output_path)

        try:
            success, err = convert_subtitle(input_file, output_path, target_format, progress_callback)
            return {"status": "success" if success else "error", "output_path": output_path, "message": err}
        except Exception as e:
            logger.error(f"字幕格式转换异常: {e}")
            return {"status": "error", "message": str(e)}

    def subtitle_split_api(self, input_file: str,
                           output_dir: str = "", output_name: str = "",
                           pattern=None, progress_callback=None) -> Dict:
        """拆分双语字幕"""
        if not os.path.exists(input_file):
            return {"status": "error", "message": "文件不存在"}

        if not output_dir:
            output_dir = os.path.dirname(input_file)
        ext = os.path.splitext(input_file)[1]
        if output_name:
            base_name = os.path.splitext(output_name)[0]
        else:
            base_name = os.path.splitext(os.path.basename(input_file))[0]
        output_path_a = os.path.join(output_dir, f"{base_name}_A{ext}")
        output_path_b = os.path.join(output_dir, f"{base_name}_B{ext}")
        output_path_a = self._resolve_conflict(output_path_a)
        output_path_b = self._resolve_conflict(output_path_b)

        try:
            success, err = split_bilingual(input_file, output_path_a, output_path_b, pattern, progress_callback)
            return {
                "status": "success" if success else "error",
                "output_path_a": output_path_a,
                "output_path_b": output_path_b,
                "message": err,
            }
        except Exception as e:
            logger.error(f"双语字幕拆分异常: {e}")
            return {"status": "error", "message": str(e)}

    def subtitle_extract_api(self, input_file: str,
                             output_dir: str = "", output_name: str = "",
                             stream_index: int = 0, output_format: str = "srt",
                             progress_callback=None) -> Dict:
        """从视频提取内嵌字幕"""
        if not os.path.exists(input_file):
            return {"status": "error", "message": "文件不存在"}

        fmt = output_format.lower().lstrip(".")
        if not output_dir:
            output_dir = os.path.dirname(input_file)
        if output_name:
            name = os.path.splitext(output_name)[0]
        else:
            name = os.path.splitext(os.path.basename(input_file))[0]
        output_path = os.path.join(output_dir, f"{name}.{fmt}")
        output_path = self._resolve_conflict(output_path)

        try:
            success, err = extract_from_video(input_file, output_path, stream_index, progress_callback)
            return {"status": "success" if success else "error", "output_path": output_path, "message": err}
        except Exception as e:
            logger.error(f"字幕提取异常: {e}")
            return {"status": "error", "message": str(e)}

    def get_video_preview(self, filepath: str) -> Dict:
        """获取视频预览信息（截图 + 元数据，并行执行）"""
        if not os.path.exists(filepath):
            return {"status": "error", "message": "文件不存在"}

        with TPE(max_workers=2) as pool:
            detail_future = pool.submit(get_video_detail, filepath)
            screenshot_future = pool.submit(extract_screenshot, filepath)
            detail = detail_future.result()
            tmp_path = screenshot_future.result()

        screenshot_b64 = None
        if tmp_path:
            try:
                with open(tmp_path, "rb") as f:
                    screenshot_b64 = base64.b64encode(f.read()).decode("ascii")
            except Exception:
                pass
            finally:
                try:
                    os.remove(tmp_path)
                except OSError:
                    pass

        bitrate_str = f"{detail.bitrate // 1000} kbps" if detail.bitrate > 0 else "未知"
        dur_m, dur_s = divmod(int(detail.duration), 60)
        dur_str = f"{dur_m:02d}:{dur_s:02d}" if detail.duration > 0 else "未知"
        resolution = f"{detail.width}x{detail.height}" if detail.width else "未知"

        # 集数检测
        from fisheep_video_merger.core.matcher import extract_episode_number
        ep = extract_episode_number(os.path.basename(filepath))
        ep_str = f"第{ep}集" if ep else None

        # 来源平台检测
        platform = "通用"
        source_dir = os.path.dirname(filepath)
        from fisheep_video_merger.core.matcher import read_bilibili_meta
        if read_bilibili_meta(source_dir):
            platform = "B站"
        elif any(os.path.exists(os.path.join(source_dir, f)) for f in ["entry.json", "danmaku.xml"]):
            platform = "B站"
        elif filepath.lower().endswith(".webm"):
            platform = "YouTube"
        elif filepath.lower().endswith(".m4s"):
            platform = "B站"

        return {
            "status": "success" if not detail.error else "error",
            "message": detail.error,
            "screenshot": screenshot_b64,
            "resolution": resolution,
            "video_codec": detail.video_codec or "未知",
            "audio_codec": detail.audio_codec or "未知",
            "bitrate": bitrate_str,
            "duration": dur_str,
            "fps": f"{detail.fps:.0f}" if detail.fps > 0 else "未知",
            "episode": ep_str,
            "platform": platform,
            "error": detail.error,
        }

    def get_file_info(self, filepath: str) -> Dict:
        """获取音频文件详细信息（编码/码率/声道/采样率/时长）"""
        if not os.path.exists(filepath):
            return {"status": "error", "message": "文件不存在"}
        try:
            from fisheep_video_merger.utils.ffprobe import get_ffprobe_path, _probe_file
            data = _probe_file(filepath, extra_args=["-show_format"])
            if data is None:
                return {"status": "error", "message": "ffprobe 调用失败"}

            audio_streams = [s for s in data.get("streams", []) if s.get("codec_type") == "audio"]
            fmt = data.get("format", {})

            if audio_streams:
                a = audio_streams[0]
                duration = float(a.get("duration", 0) or fmt.get("duration", 0) or 0)
                bitrate_raw = a.get("bit_rate") or fmt.get("bit_rate") or 0
                return {
                    "status": "success",
                    "codec": a.get("codec_name", "未知"),
                    "bitrate": int(bitrate_raw) // 1000 if bitrate_raw else 0,
                    "channels": a.get("channels", 0),
                    "channel_layout": a.get("channel_layout", "未知"),
                    "sample_rate": a.get("sample_rate", "未知"),
                    "duration": duration,
                    "duration_str": self._format_duration(duration) if duration > 0 else None,
                    "name": os.path.basename(filepath),
                    "filepath": filepath,
                    "size": f"{os.path.getsize(filepath) / (1024*1024):.1f} MB",
                }
            return {"status": "error", "message": "未找到音频流"}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def get_hw_accel_info(self) -> Dict:
        """获取硬件加速信息"""
        from fisheep_video_merger.core.ffmpeg_runner import detect_hw_accel
        info = detect_hw_accel()
        return {"status": "success", **info}

    def _resolve_conflict(self, output_path: str) -> str:
        """检查输出文件是否存在，若存在则自动重命名避免覆盖"""
        if not os.path.exists(output_path):
            return output_path
        base, ext = os.path.splitext(output_path)
        for i in range(1, 10000):
            new_path = f"{base}_{i}{ext}"
            if not os.path.exists(new_path):
                return new_path
        return output_path

    def _format_duration(self, seconds: float) -> str:
        """将秒数格式化为 HH:MM:SS"""
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        s = int(seconds % 60)
        return f"{h:02d}:{m:02d}:{s:02d}"
