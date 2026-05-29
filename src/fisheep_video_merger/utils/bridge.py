"""
🐑 Fisheep 视频工具箱 - Python-JS 桥接模块 (Bridge)
提供纯 Python 实现的桌面操作系统级交互（文件/目录选择）与多线程高并发合并控制
支持 B站/YouTube/通用音视频文件的扫描、配对、合并及工具操作
"""

import os
import re
import json
import time
import logging
import threading
import subprocess
from typing import Optional, List, Dict
from concurrent.futures import ThreadPoolExecutor, CancelledError

try:
    import send2trash
except ImportError:
    send2trash = None

import webview

# 日志查看器最大显示条数
MAX_DISPLAYED_LOGS = 200

from fisheep_video_merger.core.matcher import (
    MergeTask,
    MatchResult,
    auto_match,
    create_manual_task,
)
from fisheep_video_merger.core.scanner import scan_multiple_directories
from fisheep_video_merger.core.merger import merge_single
from fisheep_video_merger.core.converter import convert_single
from fisheep_video_merger.core.extractor import extract_audio as extract_audio_fn
from fisheep_video_merger.core.compressor import compress_video as compress_video_fn
from fisheep_video_merger.core.trimmer import trim_video as trim_video_fn
from fisheep_video_merger.utils.ffprobe import analyze_file, StreamInfo, StreamType
from fisheep_video_merger.utils.logger import get_logger

logger = get_logger()


class UIBridge:
    """
    JS API Bridge 类
    暴露给 pywebview window 的所有方法将被 JS 中以 window.pywebview.api.methodName() 调用
    """

    def __init__(self):
        self._window: Optional[webview.Window] = None
        self.root_paths: List[str] = []
        self.all_stream_infos: List[StreamInfo] = []
        self.muxed_files: List[StreamInfo] = []

        self.tasks: List[MergeTask] = []

        # 合并取消支持
        self._cancel_event = threading.Event()
        self._executor: Optional[ThreadPoolExecutor] = None
        self._futures: List = []
        self._active_processes: Dict[int, subprocess.Popen] = {}
        self.pending_videos: List[StreamInfo] = []
        self.pending_audios: List[StreamInfo] = []
        
        self.is_merging = False
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
            # 工具输出目录
            "tool_output_dirs": {
                "convert": "",
                "extract": "",
                "compress": "",
                "trim": ""
            },
            # 工具设置
            "tool_settings": {
                "convert": {"format": "mp4", "mode": "copy"},
                "extract": {"format": "aac", "bitrate": "192k"},
                "compress": {"preset": "medium", "resolution": "720p"},
                "trim": {"mode": "reencode"}
            },
            # 窗口位置
            "window_x": None,
            "window_y": None,
            "window_width": 1100,
            "window_height": 700
        }
        
        # 线程锁
        self._lock = threading.Lock()
        
        # 加载历史工作状态
        self._load_workspace_state()

    def set_window(self, window: webview.Window):
        """挂载 pywebview Window 句柄，用于 evaluate_js 反向广播"""
        self._window = window

    # ====================================================================
    # 💾 1. 本地状态持久化存盘与无缝还原 (State Persistence)
    # ====================================================================
    
    def _get_state_file_path(self) -> str:
        """获取本地状态 JSON 文件的绝对路径 (完美继承原 PySide 路径)"""
        app_data = os.environ.get('LOCALAPPDATA')
        if app_data:
            app_dir = os.path.join(app_data, "fisheep-video-merger")
        else:
            app_dir = os.path.abspath(os.path.expanduser("~/.fisheep_video_merger"))
        os.makedirs(app_dir, exist_ok=True)
        return os.path.join(app_dir, "workspace_state.json")

    def _save_workspace_state(self):
        """将当前的工作区状态持久化写入本地 JSON（500ms 防抖）"""
        if hasattr(self, '_save_timer'):
            self._save_timer.cancel()
        self._save_timer = threading.Timer(0.5, self._do_save_workspace_state)
        self._save_timer.daemon = True
        self._save_timer.start()

    def _do_save_workspace_state(self):
        """实际执行保存"""
        with self._lock:
            try:
                state = {
                    "settings": self.settings,
                    "root_paths": self.root_paths,
                    "tasks": [],
                    "pending_videos": [],
                    "pending_audios": [],
                    "muxed_files": [],
                }

                # 1. 序列化合并任务
                for task in self.tasks:
                    state["tasks"].append({
                        "output_name": task.output_name,
                        "video_file": task.video_file,
                        "audio_file": task.audio_file,
                        "source_dir": task.source_dir,
                        "root_path": task.root_path,
                        "status": task.status,
                        "error_message": task.error_message,
                        "is_multi_episode": task.is_multi_episode,
                    })

                # 2. 序列化待整理与已完整流
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

                state["pending_videos"] = [serialize_info(x) for x in self.pending_videos]
                state["pending_audios"] = [serialize_info(x) for x in self.pending_audios]
                state["muxed_files"] = [serialize_info(x) for x in self.muxed_files]

                filepath = self._get_state_file_path()
                with open(filepath, "w", encoding="utf-8") as f:
                    json.dump(state, f, ensure_ascii=False, indent=2)
                logger.debug(f"UIBridge 工作区状态已安全写入: {filepath}")
            except Exception as e:
                logger.warning(f"UIBridge 自动保存状态失败: {e}")

    def _load_workspace_state(self):
        """读取本地 JSON 状态文件，完美还原历史工作状态"""
        filepath = self._get_state_file_path()
        if not os.path.exists(filepath):
            return

        try:
            with open(filepath, "r", encoding="utf-8") as f:
                state = json.load(f)
            
            if not isinstance(state, dict):
                return

            # 1. 还原设置
            if "settings" in state:
                self.settings.update(state["settings"])

            # 2. 还原根目录路径
            self.root_paths = state.get("root_paths", [])

            # 3. 反序列化 StreamInfo
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

            raw_pv = state.get("pending_videos", [])
            self.pending_videos = [x for x in (deserialize_info(d) for d in raw_pv) if x is not None]

            raw_pa = state.get("pending_audios", [])
            self.pending_audios = [x for x in (deserialize_info(d) for d in raw_pa) if x is not None]
            
            raw_mf = state.get("muxed_files", [])
            self.muxed_files = [x for x in (deserialize_info(d) for d in raw_mf) if x is not None]

            # 4. 同步流缓存
            self.all_stream_infos = self.pending_videos + self.pending_audios + self.muxed_files

            # 5. 还原任务队列
            self.tasks = []
            for t in state.get("tasks", []):
                try:
                    self.tasks.append(MergeTask(
                        output_name=t.get("output_name", ""),
                        video_file=t.get("video_file", ""),
                        audio_file=t.get("audio_file", ""),
                        source_dir=t.get("source_dir", ""),
                        root_path=t.get("root_path", ""),
                        status=t.get("status", "pending"),
                        error_message=t.get("error_message"),
                        is_multi_episode=bool(t.get("is_multi_episode", False)),
                    ))
                except Exception:
                    continue
            
            logger.info(f"UIBridge 成功恢复工作状态：还原了 {len(self.tasks)} 个任务")
        except Exception as e:
            logger.error(f"UIBridge 恢复本地工作状态异常: {e}")

    # ====================================================================
    # 🎛️ 2. JS 可调用 API 端点定义 (Exposed JS APIs)
    # ====================================================================

    def get_current_settings(self) -> Dict:
        """获取当前配置参数字典"""
        return self.settings

    def check_ffmpeg_status(self) -> Dict:
        """检查 FFmpeg/ffprobe 可用性，返回详细状态"""
        from fisheep_video_merger.utils.ffprobe import check_ffmpeg_available, get_ffprobe_path
        available = check_ffmpeg_available()
        path = get_ffprobe_path() if available else ""

        version = ""
        if available:
            try:
                result = subprocess.run(
                    [path, "-version"],
                    capture_output=True, text=True, timeout=5
                )
                if result.returncode == 0:
                    version = result.stdout.split('\n')[0].strip()
            except Exception:
                pass

        return {
            "available": available,
            "path": path,
            "version": version
        }

    def update_task_status(self, index: int, status: str) -> Dict:
        """更新指定任务的状态"""
        if 0 <= index < len(self.tasks):
            self.tasks[index].status = status
            self.tasks[index].error_message = None
            return self._get_queue_data()
        return {"status": "error", "message": "Invalid index"}

    def get_logs(self) -> Dict:
        """获取最近的日志记录"""
        from fisheep_video_merger.utils.logger import get_logs
        logs = get_logs()
        return {"logs": logs[-MAX_DISPLAYED_LOGS:]}

    def update_setting(self, key: str, value) -> Dict:
        """更新主设置项（output_dir, output_format, concurrency 等）"""
        self.settings[key] = value
        self._save_workspace_state()
        return {"status": "success"}

    def rename_task(self, index: int, new_name: str) -> Dict:
        """重命名任务输出文件名"""
        if 0 <= index < len(self.tasks):
            self.tasks[index].output_name = new_name
            return self._get_queue_data()
        return {"status": "error", "message": "Invalid index"}

    def batch_rename(self, indexes: List[int], prefix: str = "", suffix: str = "",
                     replace_from: str = "", replace_to: str = "") -> Dict:
        """批量重命名任务输出文件名"""
        count = 0
        for idx in indexes:
            if 0 <= idx < len(self.tasks):
                name = self.tasks[idx].output_name
                if replace_from:
                    name = name.replace(replace_from, replace_to)
                if prefix:
                    name = prefix + name
                if suffix:
                    name = name + suffix
                self.tasks[idx].output_name = name
                count += 1
        return {"status": "success", "renamed": count}

    def reorder_tasks(self, from_idx: int, to_idx: int) -> Dict:
        """调整任务顺序"""
        if 0 <= from_idx < len(self.tasks) and 0 <= to_idx < len(self.tasks):
            task = self.tasks.pop(from_idx)
            self.tasks.insert(to_idx, task)
            return self._get_queue_data()
        return {"status": "error", "message": "Invalid index"}

    def get_platform_stats(self) -> Dict:
        """获取已导入文件的平台分布统计"""
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

    def export_config(self) -> Dict:
        """导出当前队列配对为 JSON"""
        try:
            tasks_data = []
            for t in self.tasks:
                tasks_data.append({
                    "output_name": t.output_name,
                    "video_file": t.video_file,
                    "audio_file": t.audio_file,
                    "source_dir": t.source_dir,
                })
            config = {
                "version": "1.0",
                "tasks": tasks_data,
                "settings": {
                    "output_format": self.settings.get("output_format", "mp4"),
                    "naming_template": self.settings.get("naming_template", ""),
                }
            }
            return {"status": "success", "config": config}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def import_config(self, config: Dict) -> Dict:
        """导入配对配置"""
        try:
            from fisheep_video_merger.core.matcher import MergeTask
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
                # 去重
                if not any(t.video_file == task.video_file and t.audio_file == task.audio_file for t in self.tasks):
                    self.tasks.append(task)
                    imported += 1
            # 应用导入的设置
            imported_settings = config.get("settings", {})
            if imported_settings.get("naming_template"):
                self.settings["naming_template"] = imported_settings["naming_template"]
            self._save_workspace_state()
            return {"status": "success", "imported": imported}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def import_config_file(self) -> Dict:
        """通过文件对话框导入配置"""
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
            return self.import_config(config)
        except Exception as e:
            return {"status": "error", "message": f"读取配置失败: {e}"}

    def export_config_file(self) -> Dict:
        """通过文件对话框导出配置"""
        if not self._window:
            return {"status": "error", "message": "Window not ready"}
        result = self._window.create_file_dialog(
            webview.SAVE_DIALOG,
            save_filename="fisheep_config.json",
            file_types=('JSON 配置 (*.json)',)
        )
        if not result:
            return {"status": "cancelled"}
        try:
            config = self.export_config().get("config", {})
            with open(result, "w", encoding="utf-8") as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
            return {"status": "success", "path": result}
        except Exception as e:
            return {"status": "error", "message": f"导出失败: {e}"}

    def update_tool_setting(self, tool: str, key: str, value) -> Dict:
        """更新工具设置（convert/extract/compress/trim）"""
        if tool in self.settings.get("tool_settings", {}):
            self.settings["tool_settings"][tool][key] = value
            self._save_workspace_state()
        return {"status": "success"}

    def update_tool_output_dir(self, tool: str, path: str) -> Dict:
        """更新工具输出目录"""
        if tool in self.settings.get("tool_output_dirs", {}):
            self.settings["tool_output_dirs"][tool] = path
            self._save_workspace_state()
        return {"status": "success"}

    def update_theme(self, theme: str) -> Dict:
        """更新界面主题配置并保存"""
        self.settings["theme"] = theme
        self._save_workspace_state()
        return {"status": "success", "theme": theme}

    def select_folder_dialog(self) -> Dict:
        """弹出系统文件夹选择框，并在后台异步启动扫描任务"""
        if not self._window:
            return {"status": "error", "message": "Window context not ready"}
        
        result = self._window.create_file_dialog(webview.FOLDER_DIALOG)
        if result and len(result) > 0:
            folder = result[0]
            self._add_folders([folder])
            return self._get_queue_data()
        return {"status": "cancelled"}

    def select_files_dialog(self) -> Dict:
        """弹出系统音视频文件选择框"""
        if not self._window:
            return {"status": "error", "message": "Window context not ready"}

        result = self._window.create_file_dialog(
            webview.OPEN_DIALOG,
            allow_multiple=True,
            file_types=('音视频文件 (*.m4s;*.webm;*.mp4;*.ts;*.m4a;*.aac;*.mp3;*.flac;*.mkv;*.flv;*.mov)', '所有文件 (*.*)')
        )
        if result and len(result) > 0:
            self._add_files(result)
            return self._get_queue_data()
        return {"status": "cancelled"}

    def select_output_dir_dialog(self) -> Dict:
        """弹出输出文件夹选择框"""
        if not self._window:
            return {"status": "error", "message": "Window context not ready"}
        
        result = self._window.create_file_dialog(webview.FOLDER_DIALOG)
        if result and len(result) > 0:
            self.settings["output_dir"] = result[0]
            self._save_workspace_state()
            return {"status": "success", "output_dir": result[0]}
        return {"status": "cancelled"}

    def clear_queue(self) -> Dict:
        """清空当前队列与待整理缓存"""
        self.root_paths.clear()
        self.all_stream_infos.clear()
        self.muxed_files.clear()
        self.tasks.clear()
        self.pending_videos.clear()
        self.pending_audios.clear()
        self._save_workspace_state()
        return self._get_queue_data()

    def get_current_state(self) -> Dict:
        """获取当前完整的工作空间状态（包含任务队列、待整理、已合并列表）"""
        return self._get_queue_data()


    def delete_task(self, index: int) -> Dict:
        """删除指定索引的任务"""
        if 0 <= index < len(self.tasks):
            task = self.tasks.pop(index)
            # 同时从缓存流中移除关联的原始文件，防止重新匹配时复活
            paths_to_remove = set()
            if task.video_file: paths_to_remove.add(task.video_file)
            if task.audio_file: paths_to_remove.add(task.audio_file)
            self.all_stream_infos = [info for info in self.all_stream_infos if info.filepath not in paths_to_remove]
            
            self._save_workspace_state()
            return self._get_queue_data()
        return {"status": "error", "message": "Index out of range"}

    def delete_pending_file(self, filepath: str) -> Dict:
        """从待整理列表中移除该文件记录"""
        self.pending_videos = [x for x in self.pending_videos if x.filepath != filepath]
        self.pending_audios = [x for x in self.pending_audios if x.filepath != filepath]
        self.all_stream_infos = [x for x in self.all_stream_infos if x.filepath != filepath]
        self._save_workspace_state()
        return self._get_queue_data()

    def delete_muxed_file(self, filepath: str) -> Dict:
        """从已完整列表中移除该文件记录"""
        self.muxed_files = [x for x in self.muxed_files if x.filepath != filepath]
        self._save_workspace_state()
        return self._get_queue_data()

    def play_video(self, filepath: str) -> Dict:
        """使用系统默认播放器打开视频"""
        if os.path.exists(filepath):
            try:
                os.startfile(filepath)
                return {"status": "success"}
            except Exception as e:
                return {"status": "error", "message": str(e)}
        return {"status": "error", "message": "File not found"}

    def open_file_folder(self, filepath: str) -> Dict:
        """在系统文件管理器中定位该文件"""
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


    def on_files_dropped(self, file_paths: List[str]) -> Dict:
        """接收并解析从 OS 拖拽进 Webview 的文件或文件夹"""
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

    # ====================================================================
    # ⚡ 3. 核心多线程并发合并总线 (Pure Python Multi-threading Merge Controller)
    # ====================================================================

    def get_hw_accel_info(self) -> Dict:
        """获取硬件加速信息"""
        from fisheep_video_merger.core.ffmpeg_runner import detect_hw_accel
        info = detect_hw_accel()
        return {"status": "success", **info}

    def get_merge_estimate(self) -> Dict:
        """预估合并耗时"""
        total_size = 0
        pending_count = 0
        for t in self.tasks:
            if t.status != "completed":
                pending_count += 1
                for f in [t.video_file, t.audio_file]:
                    if f and os.path.exists(f):
                        total_size += os.path.getsize(f)
        if pending_count == 0:
            return {"status": "success", "estimate": "无待合并任务", "seconds": 0}
        # 流复制约 500MB/s，重编码约 50MB/s，合并默认流复制
        concurrency = int(self.settings.get("concurrency", 2))
        speed_mbps = 500  # 流复制速度
        estimated_sec = (total_size / (1024 * 1024)) / speed_mbps * 60 / concurrency
        if estimated_sec < 60:
            time_str = f"约 {max(1, int(estimated_sec))} 秒"
        else:
            time_str = f"约 {int(estimated_sec // 60)} 分 {int(estimated_sec % 60)} 秒"
        return {"status": "success", "estimate": time_str, "seconds": int(estimated_sec), "tasks": pending_count, "size_mb": round(total_size / (1024*1024), 1)}

    def start_merging(self) -> Dict:
        """拉起纯 Python 高并发合并任务队列"""
        if self.is_merging:
            return {"status": "error", "message": "Merge process already running"}

        if not self.tasks:
            return {"status": "error", "message": "No tasks in queue"}

        # 显示预估时间
        est = self.get_merge_estimate()
        if est.get("estimate"):
            est_msg = f"⏱️ {est['estimate']}（{est['tasks']} 个任务，{est['size_mb']} MB）"
            self._evaluate_js_safe(f"showToast('{est_msg}', 'info')")

        # 启动后台合并总线线程以避免卡死 UI
        merge_thread = threading.Thread(target=self._run_merge_loop, daemon=True)
        merge_thread.start()
        return {"status": "success"}

    def _run_merge_loop(self):
        """执行后台并发合并循环"""
        self.is_merging = True
        self._cancel_event.clear()
        self._active_processes.clear()
        concurrency = int(self.settings.get("concurrency", 2))

        # 更新前端按钮状态为合并中
        self._evaluate_js_safe("document.getElementById('start-btn').disabled = true")
        self._evaluate_js_safe("document.getElementById('start-btn').textContent = '⚡ 正在合并队列...'")
        self._evaluate_js_safe("document.getElementById('cancel-btn').classList.remove('hidden')")

        # 初始化并渲染底部并发监视面板的卡片
        queue_data = self._get_queue_data()["tasks"]
        tasks_json = json.dumps(queue_data, ensure_ascii=False)
        self._evaluate_js_safe(f"window.initDashboardCards({tasks_json})")

        # 过滤出未完成的任务
        pending_indexes = [i for i, t in enumerate(self.tasks) if t.status != "completed"]
        
        if not pending_indexes:
            self.is_merging = False
            self._evaluate_js_safe("document.getElementById('start-btn').disabled = false")
            self._evaluate_js_safe("document.getElementById('start-btn').textContent = '🚀 开始合并队列'")
            return

        # 并发执行器
        with ThreadPoolExecutor(max_workers=concurrency) as executor:
            self._executor = executor
            self._futures = []
            for idx in pending_indexes:
                if self._cancel_event.is_set():
                    break
                task = self.tasks[idx]
                task.status = "processing"

                # 刷新前端该行显示为进度条态
                self._evaluate_js_safe(f"window.updateTaskStatus({idx}, 'processing')")

                # 提交给线程池
                future = executor.submit(self._merge_worker_thread, idx, task)
                self._futures.append(future)

            # 等待所有任务完成
            for f in self._futures:
                if self._cancel_event.is_set():
                    break
                try:
                    f.result()
                except CancelledError:
                    pass
            self._executor = None
            self._futures = []

        self.is_merging = False
        self._active_processes.clear()
        self._save_workspace_state()

        # 恢复前端按钮并刷新列表
        state_json = json.dumps(self._get_queue_data(), ensure_ascii=False)
        self._evaluate_js_safe(f"handleBackendResponse({state_json})")
        self._evaluate_js_safe("document.getElementById('start-btn').disabled = false")
        self._evaluate_js_safe("document.getElementById('start-btn').textContent = '🚀 开始合并队列'")
        self._evaluate_js_safe("document.getElementById('cancel-btn').classList.add('hidden')")

        if self._cancel_event.is_set():
            self._evaluate_js_safe("showToast('⚠️ 合并已取消', 'warning')")
        else:
            output_dir = self.settings.get("output_dir", "")
            if output_dir:
                self._evaluate_js_safe(f"showToastWithAction('🎉 所有任务已合并完成！', '📂 打开文件夹', () => window.openFileFolder('{output_dir.replace(chr(92), chr(92)+chr(92))}'))")
            else:
                self._evaluate_js_safe("showToast('🎉 所有任务已合并完成！', 'success')")

    def cancel_merging(self) -> Dict:
        """取消所有正在运行的合并任务"""
        if not self.is_merging:
            return {"status": "error", "message": "没有正在运行的合并任务"}

        self._cancel_event.set()
        logger.info("用户取消合并，正在终止所有 FFmpeg 进程...")

        # 终止所有活跃的 FFmpeg 进程
        for idx, process in list(self._active_processes.items()):
            try:
                process.kill()
                logger.info(f"已终止任务 {idx} 的 FFmpeg 进程")
            except Exception as e:
                logger.warning(f"终止任务 {idx} 进程失败: {e}")
        self._active_processes.clear()

        # 关闭线程池
        if self._executor:
            self._executor.shutdown(wait=False, cancel_futures=True)

        return {"status": "success"}

    def _merge_worker_thread(self, index: int, task: MergeTask):
        """单个 FFmpeg 任务运行线程，拦截 stderr 进度并发送 evaluate_js"""
        # 构建输出路径
        output_dir = self.settings.get("output_dir") or task.source_dir
        output_format = self.settings.get("output_format", "mp4")

        # 应用输出目录模板（按系列名创建子目录）
        dir_template = self.settings.get("output_dir_template", "").strip()
        if dir_template:
            from fisheep_video_merger.core.matcher import apply_naming_template
            sub_dir = apply_naming_template(dir_template, task.video_file, task.source_dir, task.root_path, index)
            if sub_dir:
                output_dir = os.path.join(output_dir, sub_dir)
                os.makedirs(output_dir, exist_ok=True)

        # 路径镜像：从源路径保留指定层级目录结构
        path_depth = self.settings.get("path_depth", 0)
        if path_depth > 0 and task.root_path:
            try:
                rel = os.path.relpath(task.source_dir, task.root_path)
                parts = rel.split(os.sep)
                # 过滤掉 ".." 和 "." 等无效部分
                valid_parts = [p for p in parts if p not in ("..", ".", "")]
                if valid_parts:
                    mirror_parts = valid_parts[:path_depth]
                    output_dir = os.path.join(output_dir, *mirror_parts)
                    os.makedirs(output_dir, exist_ok=True)
            except ValueError:
                pass  # 跨驱动器时 relpath 会报错

        output_filename = f"{task.output_name}.{output_format}"
        output_path = os.path.join(output_dir, output_filename)

        # 处理冲突策略
        if os.path.exists(output_path):
            if not self.settings.get("overwrite", True):
                # 如果不覆盖，则执行自动重名策略
                base, ext = os.path.splitext(output_path)
                counter = 1
                while counter < 10000:
                    new_path = f"{base}_{counter}{ext}"
                    if not os.path.exists(new_path):
                        output_path = new_path
                        break
                    counter += 1

        # 进度回调闭包
        def progress_callback(txt: str):
            # txt 类似于 "正在合并: output.mp4 (45.3%)"
            # 用正则抽取百分比
            match = re.search(r"\((\d+(?:\.\d+)?)%\)", txt)
            percent = 0.0
            if match:
                percent = float(match.group(1))
            
            # evaluate_js 毫秒级下发更新前端单个任务状态
            # (ETA与速度通过计算或简单预估，后续可进一步高阶解析)
            self._evaluate_js_safe(f"window.updateTaskProgress({index}, {percent}, '计算中...', '⚡')")

        try:
            # 调用核心 FFmpeg 单文件合并
            def on_process_created(process):
                self._active_processes[index] = process

            success, err = merge_single(
                task.video_file,
                task.audio_file,
                output_path,
                progress_callback=progress_callback,
                process_callback=on_process_created
            )

            # 清理进程引用
            self._active_processes.pop(index, None)

            if self._cancel_event.is_set():
                return

            if success:
                task.status = "completed"
                task.error_message = None
                
                # 添加到已完整列表
                from fisheep_video_merger.utils.ffprobe import StreamInfo, StreamType
                with self._lock:
                    self.muxed_files.append(StreamInfo(
                        filepath=output_path,
                        stream_type=StreamType.MUXED,
                        has_video=True,
                        has_audio=True
                    ))
                    
                self._evaluate_js_safe(f"window.updateTaskStatus({index}, 'completed')")
                
                # 可选：如果勾选合并成功删除源文件，此处标记
                if self.settings.get("delete_allowed") and send2trash:
                    try:
                        if task.video_file and os.path.exists(task.video_file):
                            send2trash.send2trash(task.video_file)
                        if task.audio_file and os.path.exists(task.audio_file):
                            send2trash.send2trash(task.audio_file)
                    except Exception as ex:
                        logger.warning(f"删除源文件失败: {ex}")
            else:
                task.status = "failed"
                task.error_message = err
                self._evaluate_js_safe(f"window.updateTaskStatus({index}, 'failed', {json.dumps(err)})")
        except Exception as e:
            task.status = "failed"
            task.error_message = str(e)
            self._evaluate_js_safe(f"window.updateTaskStatus({index}, 'failed', {json.dumps(str(e))})")

    # ====================================================================
    # ⚙️ 4. 辅助私有工具函数 (Private Helpers)
    # ====================================================================

    def _add_folders(self, directories: List[str], is_drag=False):
        """分析并批量扫描添加的文件夹记录"""
        new_directories = []
        for directory in directories:
            directory = os.path.abspath(directory)
            if not os.path.isdir(directory):
                continue
            if directory not in self.root_paths:
                self.root_paths.append(directory)
            # 无论是否已经在 root_paths 中，都加入待扫描列表以支持重复导入和刷新
            new_directories.append(directory)
        
        if not new_directories:
            return

        # 在异步后台线程开始文件夹音视频文件搜索，保证 JS 线程秒级响应
        def scan_worker():
            try:
                results = scan_multiple_directories(new_directories)
                if not results:
                    return

                # 增量存入 stream_infos 缓存
                with self._lock:
                    existing_paths = {x.filepath for x in self.all_stream_infos}
                    for info in results:
                        if info.filepath not in existing_paths:
                            self.all_stream_infos.append(info)

                    # 重新计算自动配对任务，保留已完成任务的状态
                    old_status = {}
                    for t in self.tasks:
                        if t.status in ("completed", "failed"):
                            key = (t.video_file, t.audio_file)
                            old_status[key] = (t.status, t.error_message)

                    match_result = auto_match(self.all_stream_infos, self.root_paths)
                    for new_task in match_result.auto_tasks:
                        key = (new_task.video_file, new_task.audio_file)
                        if key in old_status:
                            new_task.status, new_task.error_message = old_status[key]

                    self.tasks = match_result.auto_tasks
                    self.pending_videos = match_result.pending_videos
                    self.pending_audios = match_result.pending_audios
                    self._apply_naming_template()

                if match_result.muxed_files:
                    for m in match_result.muxed_files:
                        if not any(x.filepath == m.filepath for x in self.muxed_files):
                            self.muxed_files.append(m)

                # 自动设置输出目录
                if not self.settings.get("output_dir"):
                    if self.root_paths:
                        self.settings["output_dir"] = os.path.dirname(self.root_paths[0])

                self._save_workspace_state()

                # 异步通过 JS 重新刷新前端任务与零散文件表格
                state_json = json.dumps(self._get_queue_data(), ensure_ascii=False)
                self._evaluate_js_safe(f"handleBackendResponse({state_json})")
                
                # 给用户明确的反馈
                if len(match_result.auto_tasks) > 0 or len(match_result.pending_videos) > 0 or len(match_result.pending_audios) > 0:
                    self._evaluate_js_safe("showToast('文件夹扫描完成', 'success')")
                else:
                    self._evaluate_js_safe("showToast('选中文件夹内未发现支持的视频缓存', 'warning')")
            except Exception as e:
                logger.error(f"UIBridge 异步扫描失败: {e}")
                self._evaluate_js_safe(f"showToast('扫描失败: {json.dumps(str(e))}', 'error')")

        threading.Thread(target=scan_worker, daemon=True).start()

    def _add_files(self, filepaths: List[str]):
        """单任务添加音视频文件分析 (异步后台线程处理，防止卡死 UI)"""
        from fisheep_video_merger.core.scanner import SUPPORTED_EXTENSIONS
        def files_worker():
            try:
                # 过滤去重
                existing_paths = {x.filepath for x in self.all_stream_infos}
                new_fps = [
                    fp for fp in filepaths
                    if os.path.splitext(fp)[1].lower() in SUPPORTED_EXTENSIONS
                    and fp not in existing_paths
                ]
                if not new_fps:
                    return

                # 并行分析文件
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
                    # 保留已完成任务的状态
                    old_status = {}
                    for t in self.tasks:
                        if t.status in ("completed", "failed"):
                            key = (t.video_file, t.audio_file)
                            old_status[key] = (t.status, t.error_message)

                    match_result = auto_match(self.all_stream_infos, self.root_paths)
                    for new_task in match_result.auto_tasks:
                        key = (new_task.video_file, new_task.audio_file)
                        if key in old_status:
                            new_task.status, new_task.error_message = old_status[key]

                    self.tasks = match_result.auto_tasks
                    self.pending_videos = match_result.pending_videos
                    self.pending_audios = match_result.pending_audios
                    self._apply_naming_template()

                    # 对于已完整视频（通常不需要智能配对，但保险起见还是把新增加的合并进去）
                    # 也可以直接以 auto_match 的 muxed_files 为准
                    if new_muxed:
                        for m in new_muxed:
                            if not any(x.filepath == m.filepath for x in self.muxed_files):
                                self.muxed_files.append(m)
                    
                    self._save_workspace_state()
                
                # 刷新前端
                state_json = json.dumps(self._get_queue_data(), ensure_ascii=False)
                self._evaluate_js_safe(f"handleBackendResponse({state_json})")
                
                # 给用户友好的提示，特别是当单文件进入待整理队列时
                if len(new_videos) + len(new_audios) > 0:
                    if len(self.tasks) > old_tasks_count:
                        pass # 有新任务进入合并队列，用户能直观看到
                    else:
                        self._evaluate_js_safe("showToast('导入的片段由于缺少对应音/视频，已自动归入【待整理】队列', 'warning')")
                elif len(new_muxed) > 0:
                    self._evaluate_js_safe("showToast('导入的视频已是完整文件，自动归入【已完整】队列', 'info')")
            except Exception as e:
                logger.error(f"UIBridge 异步添加文件失败: {e}")
                self._evaluate_js_safe(f"showToast('添加文件失败: {json.dumps(str(e))}', 'error')")

        threading.Thread(target=files_worker, daemon=True).start()

    def _get_queue_data(self) -> Dict:
        """生成前端渲染所需的规格数据"""
        tasks_list = []
        for i, t in enumerate(self.tasks):
            # 获取格式和大小
            fmt = self.settings.get("output_format", "mp4").upper()
            size_str = "未知"
            if task_video := getattr(t, "video_file", None):
                if os.path.exists(task_video):
                    v_size = os.path.getsize(task_video)
                    a_size = os.path.getsize(t.audio_file) if getattr(t, "audio_file", None) and os.path.exists(t.audio_file) else 0
                    size_str = f"{(v_size + a_size) / (1024*1024):.1f} MB"

            # 源文件名（不含路径）
            source_name = os.path.basename(t.video_file) if getattr(t, "video_file", None) else ""

            tasks_list.append({
                "name": t.output_name,
                "source_name": source_name,
                "video_file": getattr(t, "video_file", "") or "",
                "audio_file": getattr(t, "audio_file", "") or "",
                "format": fmt,
                "resolution": "1080P" if "1080" in t.output_name else "自动识别",
                "size": size_str,
                "status": t.status,
                "error": t.error_message
            })

        # 待整理零散文件 (pending_videos + pending_audios)
        pending_list = []
        for info in (self.pending_videos + self.pending_audios):
            size_str = "未知"
            mtime_str = "未知"
            if os.path.exists(info.filepath):
                stat = os.stat(info.filepath)
                size_str = f"{stat.st_size / (1024*1024):.1f} MB"
                mtime_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(stat.st_mtime))
            pending_list.append({
                "filepath": info.filepath,
                "name": os.path.basename(info.filepath),
                "size": size_str,
                "mtime": mtime_str,
                "stream_type": info.stream_type.value
            })

        # 已完整文件
        muxed_list = []
        for info in self.muxed_files:
            size_str = "未知"
            mtime_str = "未知"
            if os.path.exists(info.filepath):
                stat = os.stat(info.filepath)
                size_str = f"{stat.st_size / (1024*1024):.1f} MB"
                mtime_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(stat.st_mtime))
            muxed_list.append({
                "filepath": info.filepath,
                "name": os.path.basename(info.filepath),
                "resolution": "1080P" if "1080" in info.filepath else "自动识别",
                "size": size_str,
                "mtime": mtime_str
            })

        return {
            "status": "success",
            "tasks": tasks_list,
            "pending": pending_list,
            "muxed": muxed_list
        }

    # ====================================================================
    # 🔧 5. 通用视频工具 API (Video Tools)
    # ====================================================================

    def copy_to_clipboard(self, text: str) -> Dict:
        """复制文字到系统剪贴板"""
        try:
            subprocess.run(['clip'], input=text.encode('utf-8'), check=True, timeout=5)
            return {"status": "success"}
        except Exception as e:
            logger.error(f"复制到剪贴板失败: {e}")
            return {"status": "error", "message": str(e)}

    def select_tool_files(self) -> Dict:
        """通用文件选择对话框，返回选中的文件路径列表"""
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

    def get_video_info(self, filepath: str) -> Dict:
        """获取视频文件详细信息（含时长）"""
        if not os.path.exists(filepath):
            return {"status": "error", "message": "文件不存在"}
        try:
            info = analyze_file(filepath)
            stat = os.stat(filepath)

            # 获取时长
            duration = None
            try:
                ffprobe_path = "ffprobe"
                result = subprocess.run(
                    [ffprobe_path, "-v", "quiet", "-show_entries", "format=duration",
                     "-of", "default=noprint_wrappers=1:nokey=1", filepath],
                    capture_output=True, text=True, timeout=10
                )
                if result.returncode == 0 and result.stdout.strip():
                    duration = float(result.stdout.strip())
            except Exception:
                pass

            return {
                "status": "success",
                "filepath": filepath,
                "name": os.path.basename(filepath),
                "size": f"{stat.st_size / (1024*1024):.1f} MB",
                "size_bytes": stat.st_size,
                "video_codec": info.video_codec,
                "audio_codec": info.audio_codec,
                "has_video": info.has_video,
                "has_audio": info.has_audio,
                "stream_type": info.stream_type.value,
                "duration": duration,
                "duration_str": self._format_duration(duration) if duration else None,
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def _format_duration(self, seconds: float) -> str:
        """将秒数格式化为 HH:MM:SS"""
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        s = int(seconds % 60)
        return f"{h:02d}:{m:02d}:{s:02d}"

    def get_file_info(self, filepath: str) -> Dict:
        """获取音频文件详细信息（编码/码率/声道/采样率/时长）"""
        if not os.path.exists(filepath):
            return {"status": "error", "message": "文件不存在"}
        try:
            from fisheep_video_merger.utils.ffprobe import get_ffprobe_path, _probe_file
            # 使用共享的 ffprobe 函数获取流信息
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
            pass
        return {"status": "success", "codec": "未知", "bitrate": 0, "channels": 0, "sample_rate": "未知", "duration": 0}

    def _make_tool_progress_callback(self, tool: str):
        """创建工具进度回调闭包（convert/extract/compress/trim 共用）"""
        def callback(txt, pct=None, eta=None, speed=None):
            self._evaluate_js_safe(
                f"window.updateToolProgress && window.updateToolProgress('{tool}', "
                f"{json.dumps(txt)}, {pct if pct is not None else 'null'})"
            )
        return callback

    def convert_file(self, input_file: str, output_format: str, mode: str, output_dir: str = "") -> Dict:
        """格式转换 API"""
        if not os.path.exists(input_file):
            return {"status": "error", "message": "文件不存在"}

        if not output_dir:
            output_dir = self.settings.get("output_dir") or os.path.dirname(input_file)
        name = os.path.splitext(os.path.basename(input_file))[0]
        output_path = os.path.join(output_dir, f"{name}.{output_format}")
        output_path = self._resolve_output_conflict(output_path)
        success, err = convert_single(input_file, output_path, mode, self._make_tool_progress_callback('convert'))
        return {"status": "success" if success else "error", "output_path": output_path, "message": err}

    def extract_audio_api(self, input_file: str, audio_format: str, bitrate: str,
                          output_dir: str = "", output_name: str = "",
                          channels: str = "original", sample_rate: str = "original",
                          volume: float = 1.0, bitrate_mode: str = "cbr") -> Dict:
        """音频提取 API"""
        if not os.path.exists(input_file):
            return {"status": "error", "message": "文件不存在"}

        if not output_dir:
            output_dir = self.settings.get("output_dir") or os.path.dirname(input_file)
        if output_name:
            name = os.path.splitext(output_name)[0]
        else:
            name = os.path.splitext(os.path.basename(input_file))[0]
        # AAC 格式输出为 M4A（MP4 容器记录精确时长，ADTS 容器时长不准）
        ext = "m4a" if audio_format == "aac" else audio_format
        output_path = os.path.join(output_dir, f"{name}.{ext}")
        output_path = self._resolve_output_conflict(output_path)
        try:
            success, err = extract_audio_fn(
                input_file, output_path, audio_format, bitrate,
                channels=channels, sample_rate=sample_rate,
                volume=volume, bitrate_mode=bitrate_mode,
                progress_callback=self._make_tool_progress_callback('extract')
            )
            return {"status": "success" if success else "error", "output_path": output_path, "message": err}
        except Exception as e:
            logger.error(f"提取音频异常: {e}")
            return {"status": "error", "message": str(e)}

    def compress_video_api(self, input_file: str, preset: str, resolution: str, output_dir: str = "", output_name: str = "") -> Dict:
        """视频压缩 API"""
        if not os.path.exists(input_file):
            return {"status": "error", "message": "文件不存在"}

        if not output_dir:
            output_dir = self.settings.get("output_dir") or os.path.dirname(input_file)
        if output_name:
            name = os.path.splitext(output_name)[0]
        else:
            name = os.path.splitext(os.path.basename(input_file))[0] + "_compressed"
        ext = os.path.splitext(input_file)[1]
        output_path = os.path.join(output_dir, f"{name}{ext}")
        output_path = self._resolve_output_conflict(output_path)
        success, err = compress_video_fn(input_file, output_path, preset, resolution, self._make_tool_progress_callback('compress'))
        return {"status": "success" if success else "error", "output_path": output_path, "message": err}

    def trim_video_api(self, input_file: str, start_time: str, end_time: str, mode: str, output_dir: str = "") -> Dict:
        """视频裁剪 API"""
        if not os.path.exists(input_file):
            return {"status": "error", "message": "文件不存在"}

        if not output_dir:
            output_dir = self.settings.get("output_dir") or os.path.dirname(input_file)
        name = os.path.splitext(os.path.basename(input_file))[0]
        ext = os.path.splitext(input_file)[1]
        output_path = os.path.join(output_dir, f"{name}_trimmed{ext}")
        output_path = self._resolve_output_conflict(output_path)
        success, err = trim_video_fn(input_file, output_path, start_time, end_time, mode=mode, progress_callback=self._make_tool_progress_callback('trim'))
        return {"status": "success" if success else "error", "output_path": output_path, "message": err}

    def get_video_preview(self, filepath: str) -> Dict:
        """获取视频预览信息（截图 + 元数据，并行执行）"""
        import base64
        from concurrent.futures import ThreadPoolExecutor as TPE
        from fisheep_video_merger.utils.ffprobe import get_video_detail, extract_screenshot

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

        # 格式化码率和时长
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

    def _apply_naming_template(self):
        """如果有命名模板设置，重新生成所有任务的输出名"""
        template = self.settings.get("naming_template", "").strip()
        if not template:
            return
        from fisheep_video_merger.core.matcher import apply_naming_template
        for i, task in enumerate(self.tasks):
            task.output_name = apply_naming_template(
                template, task.video_file, task.source_dir, task.root_path, i
            )

    def _resolve_output_conflict(self, output_path: str) -> str:
        """检查输出文件是否存在，若存在则自动重命名避免覆盖"""
        if not os.path.exists(output_path):
            return output_path
        base, ext = os.path.splitext(output_path)
        for i in range(1, 10000):
            new_path = f"{base}_{i}{ext}"
            if not os.path.exists(new_path):
                return new_path
        return output_path

    def _evaluate_js_safe(self, code: str):
        """线程安全地在 Webview window 中执行 JS"""
        if self._window:
            try:
                # pywebview 的 evaluate_js 是非阻塞的，可直接从子线程安全调用
                self._window.evaluate_js(code)
            except Exception as e:
                logger.debug(f"Evaluate JS failed (probably window closed): {e}")
