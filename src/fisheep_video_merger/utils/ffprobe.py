"""
ffprobe 封装模块
负责调用 ffprobe 解析 m4s 文件的流类型
"""

import json
import subprocess
from enum import Enum
from dataclasses import dataclass
from typing import Optional


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


def get_ffprobe_path() -> str:
    """获取 ffprobe 可执行文件路径"""
    return "ffprobe"


def check_ffmpeg_available() -> bool:
    """检查 ffmpeg/ffprobe 是否可用"""
    try:
        subprocess.run(
            ["ffprobe", "-version"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=True,
        )
        return True
    except (subprocess.SubprocessError, FileNotFoundError):
        return False


def analyze_file(filepath: str) -> StreamInfo:
    """
    分析单个 m4s 文件的流类型

    调用 ffprobe 获取文件的流信息，判断是纯视频、纯音频还是混合流。

    Args:
        filepath: m4s 文件的绝对路径

    Returns:
        StreamInfo 对象，包含流类型分析结果
    """
    try:
        cmd = [
            get_ffprobe_path(),
            "-v", "quiet",
            "-print_format", "json",
            "-show_streams",
            filepath,
        ]
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
            timeout=30,
        )
        data = json.loads(result.stdout)
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

        return StreamInfo(
            filepath=filepath,
            stream_type=stream_type,
            has_video=has_video,
            has_audio=has_audio,
            video_codec=video_codec,
            audio_codec=audio_codec,
        )

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
