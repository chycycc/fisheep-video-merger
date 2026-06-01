"""
数据模型模块
定义合并任务和配对结果的数据类
"""

from dataclasses import dataclass, field
from typing import Optional, List

from fisheep_video_merger.utils.ffprobe import StreamInfo


@dataclass
class MergeTask:
    """单个合并任务"""
    output_name: str
    video_file: str
    audio_file: str
    source_dir: str  # 源文件所在目录
    root_path: str   # 所属的拖入根目录
    status: str = "pending"  # pending / completed / failed
    error_message: Optional[str] = None
    is_multi_episode: bool = False
    output_path: Optional[str] = None


@dataclass
class MatchResult:
    """配对结果"""
    auto_tasks: List[MergeTask] = field(default_factory=list)
    pending_videos: List[StreamInfo] = field(default_factory=list)
    pending_audios: List[StreamInfo] = field(default_factory=list)
    muxed_files: List[StreamInfo] = field(default_factory=list)
