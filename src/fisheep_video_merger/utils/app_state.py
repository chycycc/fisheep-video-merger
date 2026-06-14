"""
应用状态容器
集中管理共享状态，避免通过 dict 传递
"""

from typing import List, Dict, Optional, Any

from fisheep_video_merger.utils.ffprobe import StreamInfo
from fisheep_video_merger.utils.services.state_persistence import StatePersistenceService


def _serialize_stream_info(info: StreamInfo) -> Dict:
    """序列化 StreamInfo 为可保存的字典"""
    return {
        "filepath": info.filepath,
        "stream_type": info.stream_type.value,
        "has_video": info.has_video,
        "has_audio": info.has_audio,
        "video_codec": info.video_codec,
        "audio_codec": info.audio_codec,
        "error": info.error,
    }


class AppState:
    """应用全局状态容器"""

    def __init__(self, state_persistence: StatePersistenceService):
        self.root_paths: List[str] = []
        self.all_stream_infos: List[StreamInfo] = []
        self.muxed_files: List[StreamInfo] = []
        self.pending_videos: List[StreamInfo] = []
        self.pending_audios: List[StreamInfo] = []
        self.settings: Dict = {}
        self._state_persistence = state_persistence
        self._task_mgr: Optional[Any] = None  # 延迟注入，避免循环依赖

    def set_task_manager(self, task_mgr):
        """注入任务管理器（用于序列化任务状态）"""
        self._task_mgr = task_mgr

    def save_debounced(self):
        """延迟保存工作区状态"""
        self._state_persistence.save_debounced(self.build_state())

    def save_immediate(self):
        """立即保存工作区状态"""
        self._state_persistence.save(self.build_state())

    def build_state(self) -> Dict:
        """构建可序列化的状态快照"""
        state = {
            "settings": self.settings,
            "root_paths": self.root_paths,
            "pending_videos": [_serialize_stream_info(x) for x in self.pending_videos],
            "pending_audios": [_serialize_stream_info(x) for x in self.pending_audios],
            "muxed_files": [_serialize_stream_info(x) for x in self.muxed_files],
        }
        if self._task_mgr:
            state["tasks"] = self._task_mgr.serialize_tasks()
        return state
