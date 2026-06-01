"""
对话框服务
负责文件/文件夹选择对话框
"""

import os
import json
from typing import Dict, List, Optional

import webview

from fisheep_video_merger.utils.logger import get_logger

logger = get_logger()


class DialogService:
    """文件/文件夹选择对话框"""

    def __init__(self):
        self._window: Optional[webview.Window] = None

    def set_window(self, window: webview.Window):
        """挂载 pywebview Window 句柄"""
        self._window = window

    def select_folder_dialog(self) -> Dict:
        """打开文件夹选择对话框"""
        if not self._window:
            return {"status": "error", "message": "Window not ready"}
        result = self._window.create_file_dialog(
            webview.FOLDER_DIALOG,
            allow_multiple=True
        )
        if result and len(result) > 0:
            return {"status": "success", "folders": list(result)}
        return {"status": "cancelled"}

    def select_files_dialog(self) -> Dict:
        """打开文件选择对话框"""
        if not self._window:
            return {"status": "error", "message": "Window not ready"}
        result = self._window.create_file_dialog(
            webview.OPEN_DIALOG,
            allow_multiple=True,
            file_types=('音视频文件 (*.m4s;*.webm;*.mp4;*.ts;*.m4a;*.aac;*.mp3;*.flac;*.mkv;*.flv;*.mov)', '所有文件 (*.*)')
        )
        if result and len(result) > 0:
            return {"status": "success", "files": list(result)}
        return {"status": "cancelled"}

    def select_output_dir_dialog(self) -> Dict:
        """打开输出目录选择对话框"""
        if not self._window:
            return {"status": "error", "message": "Window not ready"}
        result = self._window.create_file_dialog(
            webview.FOLDER_DIALOG,
            allow_multiple=False
        )
        if result and len(result) > 0:
            return {"status": "success", "output_dir": result[0]}
        return {"status": "cancelled"}

    def select_tool_files(self) -> Dict:
        """打开工具文件选择对话框"""
        if not self._window:
            return {"status": "error", "message": "Window not ready"}
        result = self._window.create_file_dialog(
            webview.OPEN_DIALOG,
            allow_multiple=True,
            file_types=('视频文件 (*.mp4;*.mkv;*.flv;*.mov;*.avi;*.webm;*.m4s;*.ts;*.wmv)', '所有文件 (*.*)')
        )
        if result and len(result) > 0:
            return {"status": "success", "files": list(result)}
        return {"status": "cancelled"}

    def export_config_file(self, config: Dict) -> Dict:
        """导出配置文件对话框"""
        if not self._window:
            return {"status": "error", "message": "Window not ready"}
        result = self._window.create_file_dialog(
            webview.SAVE_DIALOG,
            save_filename="fisheep_config.json",
            file_types=('JSON 配置 (*.json)',)
        )
        if not result:
            return {"status": "cancelled"}
        
        save_path = result[0] if isinstance(result, (list, tuple)) else result
        try:
            with open(save_path, "w", encoding="utf-8") as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
            return {"status": "success", "path": save_path}
        except Exception as e:
            return {"status": "error", "message": f"导出失败: {e}"}

    def import_config_file(self) -> Dict:
        """导入配置文件对话框"""
        if not self._window:
            return {"status": "error", "message": "Window not ready"}
        result = self._window.create_file_dialog(
            webview.OPEN_DIALOG,
            allow_multiple=False,
            file_types=('JSON 配置 (*.json)', '所有文件 (*.*)')
        )
        if not result:
            return {"status": "cancelled"}
        try:
            with open(result[0], "r", encoding="utf-8") as f:
                config = json.load(f)
            return {"status": "success", "config": config}
        except Exception as e:
            return {"status": "error", "message": f"读取配置失败: {e}"}
