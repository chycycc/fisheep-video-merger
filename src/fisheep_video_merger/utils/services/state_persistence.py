"""
状态持久化服务
负责工作区状态的 JSON 序列化/反序列化
"""

import os
import json
import threading
from typing import Dict, List

from fisheep_video_merger.utils.logger import get_logger

logger = get_logger()


class StatePersistenceService:
    """工作区状态持久化（JSON 文件读写，500ms 防抖）"""

    def __init__(self):
        self._save_timer: threading.Timer = None

    def get_state_file_path(self) -> str:
        """获取本地状态 JSON 文件的绝对路径"""
        app_data = os.environ.get('LOCALAPPDATA')
        if app_data:
            app_dir = os.path.join(app_data, "fisheep-video-merger")
        else:
            app_dir = os.path.abspath(os.path.expanduser("~/.fisheep_video_merger"))
        os.makedirs(app_dir, exist_ok=True)
        return os.path.join(app_dir, "workspace_state.json")

    def save_debounced(self, state_builder):
        """500ms 防抖保存（state_builder 是一个返回 dict 的可调用对象）"""
        if self._save_timer:
            self._save_timer.cancel()
        self._save_timer = threading.Timer(0.5, self._do_save, args=[state_builder])
        self._save_timer.daemon = True
        self._save_timer.start()

    def _do_save(self, state_builder):
        """实际执行保存"""
        try:
            state = state_builder()
            filepath = self.get_state_file_path()
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(state, f, ensure_ascii=False, indent=2)
            logger.debug(f"工作区状态已保存: {filepath}")
        except Exception as e:
            logger.warning(f"保存工作区状态失败: {e}")

    def load(self) -> Dict:
        """读取本地 JSON 状态文件"""
        filepath = self.get_state_file_path()
        if not os.path.exists(filepath):
            return {}
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                state = json.load(f)
            return state if isinstance(state, dict) else {}
        except Exception as e:
            logger.error(f"读取工作区状态异常: {e}")
            return {}
