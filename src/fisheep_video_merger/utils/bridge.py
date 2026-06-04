"""
🐑 Fisheep 视频工具箱 - Python-JS 桥接模块 (Bridge)
薄门面层，将 JS 调用委托给独立的 Service 类
"""

import os
import json
import threading
import subprocess
from typing import Optional, List, Dict

try:
    import send2trash
except ImportError:
    send2trash = None

import webview

from fisheep_video_merger.core.matcher import (
    MergeTask, MatchResult, auto_match, create_manual_task,
    suggest_output_name, apply_naming_template,
)
from fisheep_video_merger.core.scanner import scan_multiple_directories
from fisheep_video_merger.utils.ffprobe import analyze_file, StreamInfo, StreamType
from fisheep_video_merger.utils.logger import get_logger
from fisheep_video_merger.utils.services.state_persistence import StatePersistenceService
from fisheep_video_merger.utils.services.task_manager import TaskManagerService
from fisheep_video_merger.utils.services.merge_controller import MergeControllerService
from fisheep_video_merger.utils.services.tool_service import ToolService
from fisheep_video_merger.utils.services.dialog_service import DialogService
from fisheep_video_merger.core.batch import BatchProcessor

logger = get_logger()

# 日志查看器最大显示条数
MAX_DISPLAYED_LOGS = 200


class UIBridge:
    """
    JS API Bridge 门面类
    暴露给 pywebview window 的所有方法将被 JS 中以 window.pywebview.api.methodName() 调用
    """

    def __init__(self):
        self._window: Optional[webview.Window] = None
        self.root_paths: List[str] = []
        self.all_stream_infos: List[StreamInfo] = []
        self.muxed_files: List[StreamInfo] = []
        self.pending_videos: List[StreamInfo] = []
        self.pending_audios: List[StreamInfo] = []

        self.settings: Dict = {
            "output_format": "mp4",
            "output_dir": "",
            "delete_allowed": False,
            "theme": "auto",
            "concurrency": 2,
            "overwrite": True,
            "naming_template": "",
            "output_dir_template": "",
            "path_depth": 0,
            "enabled_formats": [".m4s", ".webm", ".mp4", ".ts", ".flv", ".m4a", ".aac", ".mp3", ".flac", ".wav"],
            "tool_output_dirs": {"convert": "", "extract": "", "compress": "", "trim": ""},
            "tool_settings": {
                "convert": {"format": "mp4", "mode": "copy"},
                "extract": {"format": "aac", "bitrate": "192k"},
                "compress": {"preset": "balanced", "resolution": "720p"},
                "trim": {"mode": "reencode"}
            },
            "window_x": None,
            "window_y": None,
            "window_width": 1100,
            "window_height": 700,
        }

        self._lock = threading.Lock()

        # 初始化 Service 实例
        self._state = StatePersistenceService()
        self._task_mgr = TaskManagerService()
        self._merge_ctrl = MergeControllerService()
        self._tool_svc = ToolService()
        self._dialog_svc = DialogService()
        self._batch_proc = BatchProcessor()

        # 加载历史工作状态
        self._load_workspace_state()

    @property
    def tasks(self):
        return self._task_mgr.tasks

    @tasks.setter
    def tasks(self, value):
        self._task_mgr.tasks = value

    @property
    def is_merging(self):
        return self._merge_ctrl.is_merging

    def set_window(self, window: webview.Window):
        """挂载 pywebview Window 句柄"""
        self._window = window
        self._dialog_svc.set_window(window)

    # ====================================================================
    # 💾 状态持久化
    # ====================================================================

    def _get_state_file_path(self) -> str:
        return self._state.get_state_file_path()

    def _save_workspace_state(self):
        self._state.save_debounced(self._build_state)

    def _do_save_workspace_state(self):
        self._state._do_save(self._build_state)

    def _build_state(self) -> Dict:
        """构建要保存的状态字典"""
        with self._lock:
            from fisheep_video_merger.utils.ffprobe import StreamInfo as SI
            def serialize_info(info):
                return {
                    "filepath": info.filepath,
                    "stream_type": info.stream_type.value,
                    "has_video": info.has_video,
                    "has_audio": info.has_audio,
                    "video_codec": info.video_codec,
                    "audio_codec": info.audio_codec,
                    "error": info.error,
                }
            return {
                "settings": self.settings,
                "root_paths": self.root_paths,
                "tasks": self._task_mgr.serialize_tasks(),
                "pending_videos": [serialize_info(x) for x in self.pending_videos],
                "pending_audios": [serialize_info(x) for x in self.pending_audios],
                "muxed_files": [serialize_info(x) for x in self.muxed_files],
            }

    def _load_workspace_state(self):
        state = self._state.load()
        if not state:
            return
        try:
            if "settings" in state:
                self.settings.update(state["settings"])
            self.root_paths = state.get("root_paths", [])

            def deserialize_info(d):
                try:
                    st_val = d.get("stream_type", "unknown")
                    st_enum = StreamType.UNKNOWN
                    for candidate in StreamType:
                        if candidate.value == st_val:
                            st_enum = candidate
                            break
                    return StreamInfo(
                        filepath=d.get("filepath", ""),
                        stream_type=st_enum,
                        has_video=bool(d.get("has_video")),
                        has_audio=bool(d.get("has_audio")),
                        video_codec=d.get("video_codec"),
                        audio_codec=d.get("audio_codec"),
                        error=d.get("error"),
                    )
                except Exception:
                    return None

            self.pending_videos = [x for x in (deserialize_info(d) for d in state.get("pending_videos", [])) if x]
            self.pending_audios = [x for x in (deserialize_info(d) for d in state.get("pending_audios", [])) if x]
            self.muxed_files = [x for x in (deserialize_info(d) for d in state.get("muxed_files", [])) if x]
            self.all_stream_infos = self.pending_videos + self.pending_audios + self.muxed_files

            self._task_mgr.tasks = self._task_mgr.deserialize_tasks(state.get("tasks", []))
            logger.info(f"成功恢复工作状态：{len(self.tasks)} 个任务")
        except Exception as e:
            logger.error(f"恢复工作状态异常: {e}")

    # ====================================================================
    # 🎛️ 设置 API
    # ====================================================================

    def get_current_settings(self) -> Dict:
        return self.settings

    def update_setting(self, key: str, value) -> Dict:
        self.settings[key] = value
        self._save_workspace_state()
        return {"status": "success"}

    def update_tool_setting(self, tool: str, key: str, value) -> Dict:
        if tool in self.settings.get("tool_settings", {}):
            self.settings["tool_settings"][tool][key] = value
            self._save_workspace_state()
        return {"status": "success"}

    def update_tool_output_dir(self, tool: str, path: str) -> Dict:
        if tool in self.settings.get("tool_output_dirs", {}):
            self.settings["tool_output_dirs"][tool] = path
            self._save_workspace_state()
        return {"status": "success"}

    def update_theme(self, theme: str) -> Dict:
        self.settings["theme"] = theme
        self._save_workspace_state()
        return {"status": "success"}

    # ====================================================================
    # 📋 任务管理 API
    # ====================================================================

    def get_current_state(self) -> Dict:
        return self._get_queue_data()

    def delete_task(self, index: int) -> Dict:
        self._task_mgr.delete_task(index)
        self._save_workspace_state()
        return self._get_queue_data()

    def clear_queue(self) -> Dict:
        with self._lock:
            self._task_mgr.clear_all()
            self.pending_videos.clear()
            self.pending_audios.clear()
            self.muxed_files.clear()
            self.all_stream_infos.clear()
            self.root_paths.clear()
        self._save_workspace_state()
        return self._get_queue_data()

    def update_task_status(self, index: int, status: str) -> Dict:
        self._task_mgr.update_task_status(index, status)
        return self._get_queue_data()

    def reset_task(self, index: int) -> dict:
        if self._task_mgr.reset_task(index):
            return self._get_queue_data()
        return {"status": "error"}

    def rename_task(self, index: int, new_name: str) -> Dict:
        if self._task_mgr.rename_task(index, new_name):
            self._task_mgr.reset_task(index)
            return self._get_queue_data()
        return {"status": "error", "message": "Invalid index"}

    def batch_rename(self, indexes: List[int], prefix: str = "", suffix: str = "",
                     replace_from: str = "", replace_to: str = "") -> Dict:
        count = self._task_mgr.batch_rename(indexes, prefix, suffix, replace_from, replace_to)
        return {"status": "success", "renamed": count}

    def reorder_tasks(self, from_idx: int, to_idx: int) -> Dict:
        if self._task_mgr.reorder_tasks(from_idx, to_idx):
            return self._get_queue_data()
        return {"status": "error", "message": "Invalid index"}

    # ====================================================================
    # 📂 文件操作 API
    # ====================================================================

    def select_folder_dialog(self) -> Dict:
        return self._dialog_svc.select_folder_dialog()

    def select_files_dialog(self) -> Dict:
        return self._dialog_svc.select_files_dialog()

    def select_output_dir_dialog(self) -> Dict:
        return self._dialog_svc.select_output_dir_dialog()

    def select_output_dir(self) -> Dict:
        result = self._dialog_svc.select_output_dir_dialog()
        if result.get("status") == "success":
            self.settings["output_dir"] = result["output_dir"]
            self._save_workspace_state()
        return result

    def select_tool_files(self) -> Dict:
        return self._dialog_svc.select_tool_files()

    def play_video(self, filepath: str) -> Dict:
        if os.path.exists(filepath):
            try:
                os.startfile(filepath)
                return {"status": "success"}
            except Exception as e:
                return {"status": "error", "message": str(e)}
        return {"status": "error", "message": "File not found"}

    def open_file_folder(self, filepath: str) -> Dict:
        if os.path.exists(filepath):
            try:
                subprocess.Popen(
                    ["explorer", f"/select,{os.path.abspath(filepath)}"],
                    shell=False,
                )
                return {"status": "success"}
            except Exception as e:
                return {"status": "error", "message": str(e)}
        return {"status": "error", "message": "File not found"}

    def copy_to_clipboard(self, text: str) -> Dict:
        try:
            subprocess.run(['clip'], input=text.encode('utf-8'), check=True, timeout=5)
            return {"status": "success"}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    # ====================================================================
    # 📁 文件导入 API
    # ====================================================================

    def on_files_dropped(self, file_paths: List[str]) -> Dict:
        from fisheep_video_merger.core.scanner import SUPPORTED_EXTENSIONS
        folders = []
        media_files = []
        for path in file_paths:
            if os.path.isdir(path):
                folders.append(path)
            elif os.path.splitext(path)[1].lower() in SUPPORTED_EXTENSIONS:
                media_files.append(path)
        if folders:
            self._add_folders(folders, is_drag=True)
        if media_files:
            self._add_files(media_files)
        return self._get_queue_data()

    def add_folder(self, directory: str) -> Dict:
        self._add_folders([directory])
        return self._get_queue_data()

    def _add_folders(self, directories: List[str], is_drag=False):
        """扫描添加的文件夹"""
        new_directories = []
        for directory in directories:
            directory = os.path.abspath(directory)
            if not os.path.isdir(directory):
                continue
            if directory not in self.root_paths:
                self.root_paths.append(directory)
            new_directories.append(directory)

        if not new_directories:
            return

        def scan_worker():
            try:
                results = scan_multiple_directories(new_directories)
                if not results:
                    return
                with self._lock:
                    existing_paths = {x.filepath for x in self.all_stream_infos}
                    for info in results:
                        if info.filepath not in existing_paths:
                            self.all_stream_infos.append(info)

                    old_tasks = self._task_mgr.tasks.copy()
                    match_result = auto_match(self.all_stream_infos, self.root_paths)
                    self._task_mgr.preserve_status(match_result.auto_tasks)
                    self.pending_videos = match_result.pending_videos
                    self.pending_audios = match_result.pending_audios
                    self._apply_naming_template()

                    if match_result.muxed_files:
                        for m in match_result.muxed_files:
                            if not any(x.filepath == m.filepath for x in self.muxed_files):
                                self.muxed_files.append(m)

                if not self.settings.get("output_dir"):
                    if self.root_paths:
                        self.settings["output_dir"] = os.path.dirname(self.root_paths[0])

                self._save_workspace_state()
                self._send_message("state_update", self._get_queue_data())

                if len(match_result.auto_tasks) > 0 or len(match_result.pending_videos) > 0:
                    self._send_message("toast", {"message": "文件夹扫描完成", "type": "success"})
                else:
                    self._send_message("toast", {"message": "选中文件夹内未发现支持的视频缓存", "type": "warning"})
            except Exception as e:
                logger.error(f"异步扫描失败: {e}")
                self._send_message("toast", {"message": f"扫描失败: {e}", "type": "error"})

        threading.Thread(target=scan_worker, daemon=True).start()

    def _add_files(self, filepaths: List[str]):
        """添加音视频文件"""
        from fisheep_video_merger.core.scanner import SUPPORTED_EXTENSIONS

        def files_worker():
            try:
                existing_paths = {x.filepath for x in self.all_stream_infos}
                new_fps = [
                    fp for fp in filepaths
                    if os.path.splitext(fp)[1].lower() in SUPPORTED_EXTENSIONS
                    and fp not in existing_paths
                ]
                if not new_fps:
                    return

                from concurrent.futures import ThreadPoolExecutor as TPE
                with TPE(max_workers=4) as pool:
                    results = list(pool.map(analyze_file, new_fps))

                new_videos, new_audios, new_muxed = [], [], []
                with self._lock:
                    for info in results:
                        self.all_stream_infos.append(info)
                        if info.stream_type == StreamType.VIDEO_ONLY:
                            new_videos.append(info)
                        elif info.stream_type == StreamType.AUDIO_ONLY:
                            new_audios.append(info)
                        elif info.stream_type == StreamType.MUXED:
                            new_muxed.append(info)

                with self._lock:
                    old_tasks_count = len(self.tasks)
                    match_result = auto_match(self.all_stream_infos, self.root_paths)
                    self._task_mgr.preserve_status(match_result.auto_tasks)
                    self.pending_videos = match_result.pending_videos
                    self.pending_audios = match_result.pending_audios
                    self._apply_naming_template()

                    if new_muxed:
                        for m in new_muxed:
                            if not any(x.filepath == m.filepath for x in self.muxed_files):
                                self.muxed_files.append(m)

                    self._save_workspace_state()

                self._send_message("state_update", self._get_queue_data())

                if len(new_videos) + len(new_audios) > 0:
                    if len(self.tasks) > old_tasks_count:
                        pass
                    else:
                        self._send_message("toast", {"message": "导入的片段由于缺少对应音/视频，已自动归入【待整理】队列", "type": "warning"})
                elif len(new_muxed) > 0:
                    self._send_message("toast", {"message": "导入的视频已是完整文件，自动归入【已完整】队列", "type": "info"})
            except Exception as e:
                logger.error(f"添加文件失败: {e}")
                self._send_message("toast", {"message": f"添加文件失败: {e}", "type": "error"})

        threading.Thread(target=files_worker, daemon=True).start()

    # ====================================================================
    # 📦 批量处理 API
    # ====================================================================

    def batch_import(self, folders: list, series_name: str = "") -> Dict:
        """批量导入多个文件夹（异步扫描）"""
        try:
            batch = self._batch_proc.create_batch(folders, series_name)

            def scan_worker():
                try:
                    result = self._batch_proc.scan_batch(batch.id)
                    if result:
                        self._send_message("batch_scan_done", {
                            "batch_id": result.id,
                            "tasks": len(result.tasks),
                            "pending": result.pending,
                            "muxed": result.muxed,
                            "series_name": result.series_name,
                        })
                    else:
                        self._send_message("toast", {"message": "批次扫描失败", "type": "error"})
                except Exception as e:
                    logger.error(f"批量扫描失败: {e}")
                    self._send_message("toast", {"message": f"批量扫描失败: {e}", "type": "error"})

            threading.Thread(target=scan_worker, daemon=True).start()
            return {"status": "success", "batch_id": batch.id}
        except Exception as e:
            logger.error(f"批量导入失败: {e}")
            return {"status": "error", "message": str(e)}

    def batch_preview(self, batch_id: str, template: str) -> Dict:
        """预览批量命名结果"""
        try:
            previews = self._batch_proc.preview_names(batch_id, template)
            if previews is None:
                return {"status": "error", "message": "批次不存在"}
            return {"status": "success", "previews": previews}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def batch_merge(self, batch_id: str, settings: dict = None) -> Dict:
        """启动批量合并"""
        batch = self._batch_proc.get_batch(batch_id)
        if not batch:
            return {"status": "error", "message": "批次不存在"}
        if not batch.tasks:
            return {"status": "error", "message": "批次无任务"}
        # 将批次任务加入合并队列
        for task in batch.tasks:
            self._task_mgr.add_task(task)
        # 启动合并
        return self.start_merging("merge", settings)

    # ====================================================================
    # ⚡ 合并 API
    # ====================================================================

    def start_merging(self, tool: str = "merge", settings: dict = None) -> Dict:
        if self.is_merging:
            return {"status": "error", "message": "Merge process already running"}
        if not self.tasks:
            return {"status": "error", "message": "No tasks in queue"}

        if settings:
            # Update global settings from frontend
            self.settings.update(settings)
            self._save_workspace_state()

        est = self._merge_ctrl.get_merge_estimate(self.tasks, int(self.settings.get("concurrency", 2)), self.settings)
        if est.get("tasks", 0) == 0:
            self._send_message("toast", {"message": "无待合并任务", "type": "warning"})
            return {"status": "success", "message": "无待合并任务"}
        if est.get("estimate"):
            est_msg = f"⏱️ {est['estimate']}（{est['tasks']} 个任务，{est['size_mb']} MB）"
            self._send_message("toast", {"message": est_msg, "type": "info"})

        self._send_message("button_state", {"id": "global-start-btn", "disabled": True, "text": "⚡ 正在合并队列..."})

        def on_progress(index, percent, eta, speed):
            self._send_message("task_progress", {"index": index, "percent": percent, "eta": eta, "speed": speed})

        def on_status(index, status, error, output_path=''):
            self._send_message("task_status", {"index": index, "status": status, "error": error, "output_path": output_path})

        def on_done(completed, failed):
            self._active_processes_clear()
            self._save_workspace_state()
            self._send_message("state_update", self._get_queue_data())
            self._send_message("button_state", {"id": "global-start-btn", "disabled": False, "text": "🚀 开始合并队列"})
            if self._merge_ctrl._cancel_event.is_set():
                self._send_message("toast", {"message": "⚠️ 合并已取消", "type": "warning"})
            else:
                self._send_message("toast", {"message": "🎉 所有任务已合并完成！", "type": "success"})

        self._merge_ctrl.start_merge(
            self.tasks, int(self.settings.get("concurrency", 2)), self.settings,
            self._task_mgr, on_progress, on_status, on_done
        )
        return {"status": "success"}

    def cancel_merging(self) -> Dict:
        if not self.is_merging:
            return {"status": "error", "message": "没有正在运行的合并任务"}
        self._merge_ctrl.cancel_merge()
        return {"status": "success"}

    def _active_processes_clear(self):
        self._merge_ctrl._active_processes.clear()

    # ====================================================================
    # 🔧 工具 API
    # ====================================================================

    def convert_file(self, input_file: str, output_format: str, mode: str,
                     output_dir: str = "", output_name: str = "") -> Dict:
        if not output_dir:
            output_dir = self.settings.get("output_dir") or os.path.dirname(input_file)
        return self._tool_svc.convert_file(
            input_file, output_format, mode, output_dir, output_name,
            self._make_tool_progress_callback('convert')
        )

    def extract_audio_api(self, input_file: str, audio_format: str, bitrate: str,
                          output_dir: str = "", output_name: str = "",
                          channels: str = "original", sample_rate: str = "original",
                          volume: float = 1.0, bitrate_mode: str = "cbr") -> Dict:
        if not output_dir:
            output_dir = self.settings.get("output_dir") or os.path.dirname(input_file)
        return self._tool_svc.extract_audio_api(
            input_file, audio_format, bitrate, output_dir, output_name,
            channels, sample_rate, volume, bitrate_mode,
            self._make_tool_progress_callback('extract')
        )

    def compress_video_api(self, input_file: str, preset: str, resolution: str,
                           output_dir: str = "", output_name: str = "") -> Dict:
        if not output_dir:
            output_dir = self.settings.get("output_dir") or os.path.dirname(input_file)
        return self._tool_svc.compress_video_api(
            input_file, preset, resolution, output_dir, output_name,
            self._make_tool_progress_callback('compress')
        )

    def trim_video_api(self, input_file: str, start_time: str, end_time: str, mode: str,
                       output_dir: str = "", output_name: str = "") -> Dict:
        if not output_dir:
            output_dir = self.settings.get("output_dir") or os.path.dirname(input_file)
        return self._tool_svc.trim_video_api(
            input_file, start_time, end_time, mode, output_dir, output_name,
            self._make_tool_progress_callback('trim')
        )

    def get_video_preview(self, filepath: str) -> Dict:
        return self._tool_svc.get_video_preview(filepath)

    def get_file_info(self, filepath: str) -> Dict:
        return self._tool_svc.get_file_info(filepath)

    def get_hw_accel_info(self) -> Dict:
        return self._tool_svc.get_hw_accel_info()

    # ====================================================================
    # 📊 数据 API
    # ====================================================================

    def get_logs(self) -> Dict:
        from fisheep_video_merger.utils.logger import get_logs
        logs = get_logs()
        return {"logs": logs[-MAX_DISPLAYED_LOGS:]}

    def get_merge_estimate(self) -> Dict:
        return self._merge_ctrl.get_merge_estimate(self.tasks, int(self.settings.get("concurrency", 2)), self.settings)

    def get_platform_stats(self) -> Dict:
        stats = {"B站": 0, "YouTube": 0, "通用": 0}
        for info in self.all_stream_infos:
            fp = info.filepath.lower()
            if fp.endswith(".m4s"):
                stats["B站"] += 1
            elif fp.endswith(".webm"):
                stats["YouTube"] += 1
            else:
                stats["通用"] += 1
        return {"status": "success", "stats": stats, "total": len(self.all_stream_infos)}

    def check_ffmpeg_status(self) -> Dict:
        from fisheep_video_merger.utils.ffprobe import check_ffmpeg_available, get_ffprobe_path
        available = check_ffmpeg_available()
        path = get_ffprobe_path()
        return {"available": available, "path": path}

    def export_config(self) -> Dict:
        try:
            tasks_data = self._task_mgr.serialize_tasks()
            config = {
                "version": "1.0",
                "tasks": tasks_data,
                "settings": self.settings.copy()
            }
            return {"status": "success", "config": config}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def import_config(self, config: Dict) -> Dict:
        try:
            tasks_data = config.get("tasks", [])
            imported = 0
            for td in tasks_data:
                if not os.path.exists(td.get("video_file", "")):
                    continue
                task = MergeTask(
                    output_name=td["output_name"],
                    video_file=td["video_file"],
                    audio_file=td.get("audio_file", ""),
                    source_dir=td.get("source_dir", ""),
                    root_path=td.get("source_dir", ""),
                )
                if not any(t.video_file == task.video_file and t.audio_file == task.audio_file for t in self.tasks):
                    self.tasks.append(task)
                    imported += 1
            imported_settings = config.get("settings", {})
            if imported_settings:
                # Merge settings deeply or update
                self.settings.update(imported_settings)
            
            self._save_workspace_state()
            return {"status": "success", "imported": imported}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def export_config_file(self) -> Dict:
        config = self.export_config().get("config", {})
        return self._dialog_svc.export_config_file(config)

    def import_config_file(self) -> Dict:
        result = self._dialog_svc.import_config_file()
        if result.get("status") == "success":
            return self.import_config(result["config"])
        return result

    def update_settings(self, new_settings: Dict) -> Dict:
        try:
            self.settings.update(new_settings)
            self._save_workspace_state()
            return {"status": "success"}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def export_profile_file(self) -> Dict:
        try:
            profile_data = {"version": "1.0", "settings": self.settings.copy()}
            return self._dialog_svc.export_config_file(profile_data)
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def import_profile_file(self) -> Dict:
        try:
            result = self._dialog_svc.import_config_file()
            if result.get("status") == "success":
                profile_settings = result.get("config", {}).get("settings", {})
                if profile_settings:
                    self.settings.update(profile_settings)
                    self._save_workspace_state()
                    # Return the new settings so JS can update Alpine
                    return {"status": "success", "settings": self.settings}
            return result
        except Exception as e:
            return {"status": "error", "message": str(e)}

    # ====================================================================
    # 🔧 私有辅助
    # ====================================================================

    def _make_tool_progress_callback(self, tool: str):
        """创建工具进度回调闭包"""
        def callback(txt, pct=None, eta=None, speed=None):
            self._send_message("tool_progress", {"tool": tool, "text": txt, "percent": pct})
        return callback

    def _apply_naming_template(self):
        """如果有命名模板设置，重新生成所有任务的输出名"""
        template = self.settings.get("naming_template", "").strip()
        if not template:
            return
        for i, task in enumerate(self.tasks):
            task.output_name = apply_naming_template(
                template, task.video_file, task.source_dir, task.root_path, i
            )

    def _get_queue_data(self) -> Dict:
        """生成前端渲染所需的规格数据"""
        tasks_list = []
        for i, t in enumerate(self.tasks):
            fmt = self.settings.get("output_format", "mp4").upper()
            size_str = "未知"
            if task_video := getattr(t, "video_file", None):
                if os.path.exists(task_video):
                    v_size = os.path.getsize(task_video)
                    a_size = os.path.getsize(t.audio_file) if getattr(t, "audio_file", None) and os.path.exists(t.audio_file) else 0
                    size_str = f"{(v_size + a_size) / (1024*1024):.1f} MB"

            v_name = os.path.basename(t.video_file) if getattr(t, "video_file", None) else ""
            a_name = os.path.basename(t.audio_file) if getattr(t, "audio_file", None) else ""
            if v_name and a_name:
                source_name = f"🎬 {v_name} ➕ 🎵 {a_name}"
            elif v_name:
                source_name = f"🎬 {v_name}"
            elif a_name:
                source_name = f"🎵 {a_name}"
            else:
                source_name = "未知媒体"
            tasks_list.append({
                "name": t.output_name,
                "source_name": source_name,
                "video_file": getattr(t, "video_file", "") or "",
                "audio_file": getattr(t, "audio_file", "") or "",
                "format": fmt,
                "resolution": "1080P" if "1080" in t.output_name else "自动识别",
                "size": size_str,
                "status": t.status,
                "error": t.error_message,
                "source_dir": t.source_dir,
                "output_path": getattr(t, "output_path", "") or "",
            })

        pending_list = []
        for info in (self.pending_videos + self.pending_audios):
            size_str = "未知"
            mtime_str = "未知"
            if os.path.exists(info.filepath):
                stat = os.stat(info.filepath)
                size_str = f"{stat.st_size / (1024*1024):.1f} MB"
                import time
                mtime_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(stat.st_mtime))
            pending_list.append({
                "filepath": info.filepath,
                "name": os.path.basename(info.filepath),
                "size": size_str,
                "mtime": mtime_str,
                "stream_type": info.stream_type.value,
            })

        muxed_list = []
        for info in self.muxed_files:
            size_str = "未知"
            mtime_str = "未知"
            if os.path.exists(info.filepath):
                stat = os.stat(info.filepath)
                size_str = f"{stat.st_size / (1024*1024):.1f} MB"
                import time
                mtime_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(stat.st_mtime))
            muxed_list.append({
                "filepath": info.filepath,
                "name": os.path.basename(info.filepath),
                "resolution": "1080P" if "1080" in info.filepath else "自动识别",
                "size": size_str,
                "mtime": mtime_str,
            })

        return {
            "status": "success",
            "tasks": tasks_list,
            "pending": pending_list,
            "muxed": muxed_list,
        }

    def _send_message(self, msg_type: str, data: dict = None):
        """向前端发送结构化消息（替代直接拼接 JS 代码）"""
        payload = json.dumps({"type": msg_type, "data": data or {}}, ensure_ascii=False)
        self._evaluate_js_safe(f"window.__onBridgeMessage && window.__onBridgeMessage({payload})")

    def _evaluate_js_safe(self, code: str):
        """线程安全地在 Webview window 中执行 JS"""
        if self._window:
            try:
                self._window.evaluate_js(code)
            except Exception as e:
                logger.debug(f"Evaluate JS failed: {e}")

    # ====================================================================
    # 🗑️ 删除操作
    # ====================================================================

    def delete_pending_file(self, filepath: str) -> Dict:
        with self._lock:
            self.pending_videos = [v for v in self.pending_videos if v.filepath != filepath]
            self.pending_audios = [a for a in self.pending_audios if a.filepath != filepath]
            self.all_stream_infos = [x for x in self.all_stream_infos if x.filepath != filepath]
        self._save_workspace_state()
        return self._get_queue_data()

    def delete_muxed_file(self, filepath: str) -> Dict:
        with self._lock:
            self.muxed_files = [m for m in self.muxed_files if m.filepath != filepath]
            self.all_stream_infos = [x for x in self.all_stream_infos if x.filepath != filepath]
        self._save_workspace_state()
        return self._get_queue_data()

    def manual_match(self, filepaths: list[str], output_name: str = None) -> Dict:
        if len(filepaths) != 2:
            return {"status": "error", "message": "请精确勾选 1 个视频和 1 个音频"}

        try:
            with self._lock:
                v_info = None
                a_info = None

                for p in filepaths:
                    if v := next((v for v in self.pending_videos if v.filepath == p), None):
                        v_info = v
                    elif a := next((a for a in self.pending_audios if a.filepath == p), None):
                        a_info = a

                if not v_info or not a_info:
                    return {"status": "error", "message": "必须包含 1 个视频和 1 个音频文件"}

                from fisheep_video_merger.core.matcher import create_manual_task
                import os
                root = self.root_paths[0] if self.root_paths else ""
                out_name = output_name or os.path.splitext(os.path.basename(v_info.filepath))[0]

                task = create_manual_task(v_info, a_info, out_name, root)
                self._task_mgr.preserve_status([task])

                self.pending_videos = [v for v in self.pending_videos if v.filepath != v_info.filepath]
                self.pending_audios = [a for a in self.pending_audios if a.filepath != a_info.filepath]

            self._save_workspace_state()
            return self._get_queue_data()
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def auto_match_pending(self) -> Dict:
        try:
            from fisheep_video_merger.core.matcher import auto_match
            from fisheep_video_merger.utils.ffprobe import StreamType

            with self._lock:
                # Pack pending into a stream_infos list
                streams = self.pending_videos + self.pending_audios
                if not streams:
                    return {"status": "success", "message": "没有待整理文件可供配对"}

                # Perform auto match
                result = auto_match(streams, self.root_paths)

                if len(result.auto_tasks) == 0:
                    return {"status": "success", "message": "未找到符合智能配对条件的条目"}

                # Update tasks
                self._task_mgr.preserve_status(result.auto_tasks)
                self.pending_videos = result.pending_videos
                self.pending_audios = result.pending_audios

            self._save_workspace_state()

            data = self._get_queue_data()
            data["status"] = "success"
            data["message"] = f"智能配对成功，已结对 {len(result.auto_tasks)} 项"
            return data
        except Exception as e:
            return {"status": "error", "message": str(e)}


