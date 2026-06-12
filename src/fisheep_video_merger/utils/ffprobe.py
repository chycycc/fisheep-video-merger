"""
ffprobe 封装模块
负责调用 ffprobe 解析音视频文件的流类型与元数据
"""

import json
import os
import subprocess
import tempfile
import threading
from enum import Enum
from dataclasses import dataclass
from typing import Optional

# ffprobe 结果缓存 {(filepath, mtime): StreamInfo}
_probe_cache: dict[tuple, object] = {}
_probe_cache_lock = threading.Lock()
_CACHE_MAX_SIZE = 500


class StreamType(Enum):
    """流类型枚举"""
    VIDEO_ONLY = "video_only"
    AUDIO_ONLY = "audio_only"
    MUXED = "muxed"
    UNKNOWN = "unknown"


@dataclass
class StreamInfo:
    """单个文件的流信息"""
    filepath: str
    stream_type: StreamType
    has_video: bool
    has_audio: bool
    video_codec: Optional[str] = None
    audio_codec: Optional[str] = None
    error: Optional[str] = None


_probe_path: Optional[str] = None
_probe_path_lock = threading.Lock()


def _detect_probe_path() -> str:
    """检测系统中可用的流分析工具，优先 ffprobe，回退到 ffmpeg"""
    global _probe_path
    if _probe_path is not None:
        return _probe_path

    with _probe_path_lock:
        # 双重检查锁定
        if _probe_path is not None:
            return _probe_path

        for candidate in ["ffprobe", "ffmpeg"]:
            try:
                subprocess.run(
                    [candidate, "-version"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    check=True,
                )
                _probe_path = candidate
                return candidate
            except (subprocess.SubprocessError, FileNotFoundError):
                continue

        _probe_path = ""
        return ""


def get_ffprobe_path() -> str:
    """获取流分析工具路径（ffprobe 或 ffmpeg）"""
    return _detect_probe_path()


def check_ffmpeg_available() -> bool:
    """检查 ffmpeg/ffprobe 是否可用"""
    return bool(_detect_probe_path())


def analyze_file(filepath: str) -> StreamInfo:
    """
    分析单个音视频文件的流类型

    调用 ffprobe 获取文件的流信息，判断是纯视频、纯音频还是混合流。

    Args:
        filepath: 音视频文件的绝对路径

    Returns:
        StreamInfo 对象，包含流类型分析结果
    """
    # 检查缓存（基于文件路径和修改时间）
    try:
        mtime = os.path.getmtime(filepath)
        cache_key = (filepath, mtime)
        with _probe_cache_lock:
            if cache_key in _probe_cache:
                return _probe_cache[cache_key]
    except OSError:
        cache_key = None

    try:
        data = _probe_file(filepath)
        if data is None:
            return StreamInfo(
                filepath=filepath,
                stream_type=StreamType.UNKNOWN,
                has_video=False,
                has_audio=False,
                error="ffprobe 调用失败",
            )
        streams = data.get("streams", [])

        has_video = any(s.get("codec_type") == "video" for s in streams)
        has_audio = any(s.get("codec_type") == "audio" for s in streams)

        video_codec = None
        audio_codec = None
        for s in streams:
            if s.get("codec_type") == "video" and video_codec is None:
                video_codec = s.get("codec_name")
            if s.get("codec_type") == "audio" and audio_codec is None:
                audio_codec = s.get("codec_name")

        if has_video and has_audio:
            stream_type = StreamType.MUXED
        elif has_video and not has_audio:
            stream_type = StreamType.VIDEO_ONLY
        elif not has_video and has_audio:
            stream_type = StreamType.AUDIO_ONLY
        else:
            stream_type = StreamType.UNKNOWN

        result = StreamInfo(
            filepath=filepath,
            stream_type=stream_type,
            has_video=has_video,
            has_audio=has_audio,
            video_codec=video_codec,
            audio_codec=audio_codec,
        )
        # 存入缓存
        if cache_key:
            with _probe_cache_lock:
                if len(_probe_cache) >= _CACHE_MAX_SIZE:
                    # 清理最旧的一半缓存
                    keys = list(_probe_cache.keys())[:_CACHE_MAX_SIZE // 2]
                    for k in keys:
                        del _probe_cache[k]
                _probe_cache[cache_key] = result
        return result

    except subprocess.TimeoutExpired:
        return StreamInfo(
            filepath=filepath,
            stream_type=StreamType.UNKNOWN,
            has_video=False,
            has_audio=False,
            error="ffprobe 超时",
        )
    except subprocess.CalledProcessError as e:
        return StreamInfo(
            filepath=filepath,
            stream_type=StreamType.UNKNOWN,
            has_video=False,
            has_audio=False,
            error=f"ffprobe 调用失败: {e.stderr.decode('utf-8', errors='replace')[:200]}",
        )
    except (json.JSONDecodeError, FileNotFoundError, OSError) as e:
        return StreamInfo(
            filepath=filepath,
            stream_type=StreamType.UNKNOWN,
            has_video=False,
            has_audio=False,
            error=str(e),
        )


@dataclass
class VideoDetail:
    """视频详细信息"""
    filepath: str
    width: int = 0
    height: int = 0
    video_codec: str = ""
    audio_codec: str = ""
    bitrate: int = 0
    duration: float = 0.0
    fps: float = 0.0
    error: Optional[str] = None


def _probe_file(filepath: str, extra_args: list = None) -> Optional[dict]:
    """通用 ffprobe 调用，返回解析后的 JSON 或 None"""
    probe = get_ffprobe_path()
    if not probe:
        return None
    # 先拼所有输出选项，最后放 -i 和文件路径（保证 -i 后紧跟文件名）
    cmd = [probe, "-v", "quiet", "-print_format", "json", "-show_streams"]
    if extra_args:
        cmd.extend(extra_args)
    cmd.extend(["-i", filepath])
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30, check=True)
        return json.loads(result.stdout)
    except (subprocess.CalledProcessError, json.JSONDecodeError, subprocess.TimeoutExpired, FileNotFoundError):
        return None


def get_video_detail(filepath: str) -> VideoDetail:
    """获取视频详细信息（分辨率/编码/码率/时长/帧率）"""
    try:
        data = _probe_file(filepath, extra_args=["-show_format"])
        if data is None:
            return VideoDetail(filepath=filepath, error="ffprobe 调用失败")

        fmt = data.get("format", {})
        streams = data.get("streams", [])

        detail = VideoDetail(filepath=filepath)
        detail.duration = float(fmt.get("duration", 0))
        detail.bitrate = int(fmt.get("bit_rate", 0))

        for s in streams:
            if s.get("codec_type") == "video" and not detail.width:
                detail.width = s.get("width", 0)
                detail.height = s.get("height", 0)
                detail.video_codec = s.get("codec_name", "")
                # 解析帧率 r_frame_rate = "30/1" 形式
                rfr = s.get("r_frame_rate", "0/1")
                try:
                    num, den = rfr.split("/")
                    detail.fps = float(num) / float(den) if float(den) > 0 else 0
                except (ValueError, ZeroDivisionError):
                    pass
            elif s.get("codec_type") == "audio" and not detail.audio_codec:
                detail.audio_codec = s.get("codec_name", "")

        return detail

    except Exception as e:
        return VideoDetail(filepath=filepath, error=str(e))


def extract_screenshot(filepath: str) -> Optional[str]:
    """
    用 FFmpeg 截取视频第一帧，返回 PNG 临时文件路径
    调用方负责清理临时文件
    """
    try:
        from fisheep_video_merger.core.ffmpeg_runner import get_ffmpeg_path
        ffmpeg = get_ffmpeg_path()
        fd, tmp_path = tempfile.mkstemp(suffix=".png")
        os.close(fd)
        cmd = [ffmpeg, "-ss", "1", "-i", filepath, "-vframes", "1", "-y", tmp_path]
        result = subprocess.run(cmd, capture_output=True, timeout=10)
        if result.returncode == 0 and os.path.exists(tmp_path) and os.path.getsize(tmp_path) > 0:
            return tmp_path
        # 截图失败，清理临时文件
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
    except Exception:
        pass
    return None
