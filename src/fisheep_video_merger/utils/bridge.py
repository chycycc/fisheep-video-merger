"""
🐑 B站 m4s 视频合并工具 v0.4.0 - Python-JS 桥接模块 (Bridge)
提供纯 Python 实现的桌面操作系统级交互（文件/目录选择）与多线程高并发合并控制
100% 剥离 PySide 依赖，包体极致压缩，保证与历史工作区状态的无缝兼容
"""

import os
import re
import json
import time
import logging
import threading
from typing import Optional, List, Dict
from concurrent.futures import ThreadPoolExecutor

import webview

from fisheep_video_merger.core.matcher import (
    MergeTask,
    MatchResult,
    auto_match,
    create_manual_task,
)
from fisheep_video_merger.core.scanner import scan_multiple_directories
from fisheep_video_merger.core.path_utils import generate_output_path
from fisheep_video_merger.core.merger import merge_single, remux_single, ConflictStrategy
from fisheep_video_merger.utils.ffprobe import analyze_file, StreamInfo, StreamType
from fisheep_video_merger.utils.logger import get_logger

logger = get_logger()


class UIBridge:
    """
    JS API Bridge 类
    暴露给 pywebview window 的所有方法将被 JS 中以 window.pywebview.api.methodName() 调用
    """

    def __init__(self):
        self.window: Optional[webview.Window] = None
        self.root_paths: List[str] = []
        self.all_stream_infos: List[StreamInfo] = []
        self.muxed_files: List[StreamInfo] = []
        
        self.tasks: List[MergeTask] = []
        self.pending_videos: List[StreamInfo] = []
        self.pending_audios: List[StreamInfo] = []
        
        self.is_merging = False
        self.settings: Dict = {
            "output_format": "mp4",
            "output_dir": "",
            "delete_allowed": False,
            "theme": "dark",
            "concurrency": 2,
            "overwrite": True
        }
        
        # 线程锁
        self._lock = threading.Lock()
        
        # 加载历史工作状态
        self._load_workspace_state()

    def set_window(self, window: webview.Window):
        """挂载 pywebview Window 句柄，用于 evaluate_js 反向广播"""
        self.window = window

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
        """将当前的工作区状态同步持久化写入本地 JSON"""
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

    def select_folder_dialog(self) -> Dict:
        """弹出系统文件夹选择框，并在后台异步启动扫描任务"""
        if not self.window:
            return {"status": "error", "message": "Window context not ready"}
        
        result = self.window.create_file_dialog(webview.FOLDER_DIALOG)
        if result and len(result) > 0:
            folder = result[0]
            self._add_folders([folder])
            return self._get_queue_data()
        return {"status": "cancelled"}

    def select_files_dialog(self) -> Dict:
        """弹出系统 m4s 文件选择框"""
        if not self.window:
            return {"status": "error", "message": "Window context not ready"}
        
        result = self.window.create_file_dialog(
            webview.OPEN_DIALOG,
            allow_multiple=True,
            file_types=('m4s files (*.m4s)', 'All files (*.*)')
        )
        if result and len(result) > 0:
            self._add_files(result)
            return self._get_queue_data()
        return {"status": "cancelled"}

    def select_output_dir_dialog(self) -> Dict:
        """弹出输出文件夹选择框"""
        if not self.window:
            return {"status": "error", "message": "Window context not ready"}
        
        result = self.window.create_file_dialog(webview.FOLDER_DIALOG)
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
        return {"status": "success"}

    def delete_task(self, index: int) -> Dict:
        """删除指定索引的任务"""
        if 0 <= index < len(self.tasks):
            self.tasks.pop(index)
            self._save_workspace_state()
            return self._get_queue_data()
        return {"status": "error", "message": "Index out of range"}

    def on_files_dropped(self, file_paths: List[str]) -> Dict:
        """接收并解析从 OS 拖拽进 Webview 的文件或文件夹"""
        folders = []
        m4s_files = []
        for path in file_paths:
            if os.path.isdir(path):
                folders.append(path)
            elif path.lower().endswith(".m4s"):
                m4s_files.append(path)

        if folders:
            self._add_folders(folders, is_drag=True)
        if m4s_files:
            self._add_files(m4s_files)

        return self._get_queue_data()

    # ====================================================================
    # ⚡ 3. 核心多线程并发合并总线 (Pure Python Multi-threading Merge Controller)
    # ====================================================================

    def start_merging(self) -> Dict:
        """拉起纯 Python 高并发合并任务队列"""
        if self.is_merging:
            return {"status": "error", "message": "Merge process already running"}
        
        if not self.tasks:
            return {"status": "error", "message": "No tasks in queue"}

        # 启动后台合并总线线程以避免卡死 UI
        merge_thread = threading.Thread(target=self._run_merge_loop, daemon=True)
        merge_thread.start()
        return {"status": "success"}

    def _run_merge_loop(self):
        """执行后台并发合并循环"""
        self.is_merging = True
        concurrency = int(self.settings.get("concurrency", 2))
        
        # 更新前端按钮状态为合并中
        self._evaluate_js_safe("document.getElementById('start-btn').disabled = true")
        self._evaluate_js_safe("document.getElementById('start-btn').textContent = '⚡ 正在合并队列...'")

        # 过滤出未完成的任务
        pending_indexes = [i for i, t in enumerate(self.tasks) if t.status != "completed"]
        
        if not pending_indexes:
            self.is_merging = False
            self._evaluate_js_safe("document.getElementById('start-btn').disabled = false")
            self._evaluate_js_safe("document.getElementById('start-btn').textContent = '🚀 开始合并队列'")
            return

        # 并发执行器
        with ThreadPoolExecutor(max_workers=concurrency) as executor:
            futures = []
            for idx in pending_indexes:
                task = self.tasks[idx]
                task.status = "processing"
                
                # 刷新前端该行显示为进度条态
                self._evaluate_js_safe(f"window.updateTaskStatus({idx}, 'processing')")
                
                # 提交给线程池
                future = executor.submit(self._merge_worker_thread, idx, task)
                futures.append(future)

            # 等待所有任务完成
            for f in futures:
                f.result()

        self.is_merging = False
        self._save_workspace_state()
        
        # 恢复前端按钮
        self._evaluate_js_safe("document.getElementById('start-btn').disabled = false")
        self._evaluate_js_safe("document.getElementById('start-btn').textContent = '🚀 开始合并队列'")
        self._evaluate_js_safe("showToast('🎉 所有任务已合并完成！', 'success')")

    def _merge_worker_thread(self, index: int, task: MergeTask):
        """单个 FFmpeg 任务运行线程，拦截 stderr 进度并发送 evaluate_js"""
        # 构建输出路径
        output_dir = self.settings.get("output_dir") or task.source_dir
        output_format = self.settings.get("output_format", "mp4")
        
        output_filename = f"{task.output_name}.{output_format}"
        output_path = os.path.join(output_dir, output_filename)

        # 处理冲突策略
        if os.path.exists(output_path):
            if not self.settings.get("overwrite", True):
                # 如果不覆盖，则执行自动重名策略
                base, ext = os.path.splitext(output_path)
                counter = 1
                while True:
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
            success, err = merge_single(
                task.video_file,
                task.audio_file,
                output_path,
                progress_callback=progress_callback
            )
            
            if success:
                task.status = "completed"
                task.error_message = None
                self._evaluate_js_safe(f"window.updateTaskStatus({index}, 'completed')")
                
                # 可选：如果勾选合并成功删除源文件，此处标记
                if self.settings.get("delete_source"):
                    try:
                        # 用 send2trash 安全丢进回收站，或者直接 os.remove
                        import send2trash
                        if os.path.exists(task.video_file):
                            send2trash.send2trash(task.video_file)
                        if os.path.exists(task.audio_file):
                            send2trash.send2trash(task.audio_file)
                    except Exception as ex:
                        logger.warning(f"删除源文件失败: {ex}")
            else:
                task.status = "failed"
                task.error_message = err
                self._evaluate_js_safe(f"window.updateTaskStatus({index}, 'failed', '{err}')")
        except Exception as e:
            task.status = "failed"
            task.error_message = str(e)
            self._evaluate_js_safe(f"window.updateTaskStatus({index}, 'failed', '{e}')")

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
                new_directories.append(directory)
        
        if not new_directories:
            return

        # 在异步后台线程开始文件夹 m4s 文件搜索，保证 JS 线程秒级响应
        def scan_worker():
            try:
                results = scan_multiple_directories(new_directories)
                if not results:
                    return

                # 增量存入 stream_infos 缓存
                existing_paths = {x.filepath for x in self.all_stream_infos}
                for info in results:
                    if info.filepath not in existing_paths:
                        self.all_stream_infos.append(info)

                # 重新计算自动配对任务
                match_result = auto_match(self.all_stream_infos, self.root_paths)
                self.tasks = match_result.auto_tasks
                self.pending_videos = match_result.pending_videos
                self.pending_audios = match_result.pending_audios
                self.muxed_files = match_result.muxed_files

                # 自动设置输出目录
                if not self.settings.get("output_dir"):
                    if self.root_paths:
                        self.settings["output_dir"] = os.path.dirname(self.root_paths[0])

                self._save_workspace_state()

                # 异步通过 JS 重新刷新前端任务表格
                tasks_json = json.dumps(self._get_queue_data()["tasks"], ensure_ascii=False)
                self._evaluate_js_safe(f"renderQueue({tasks_json})")
                self._evaluate_js_safe(f"showToast('📂 导入扫描成功！共发现 {len(self.tasks)} 个配对任务', 'success')")
            except Exception as e:
                logger.error(f"UIBridge 异步扫描失败: {e}")
                self._evaluate_js_safe(f"showToast('扫描失败: {e}', 'error')")

        threading.Thread(target=scan_worker, daemon=True).start()

    def _add_files(self, filepaths: List[str]):
        """单任务添加 m4s 文件分析"""
        new_videos, new_audios, new_muxed = [], [], []

        for fp in filepaths:
            if not fp.lower().endswith(".m4s"):
                continue
            info = analyze_file(fp)
            self.all_stream_infos.append(info)
            if info.stream_type == StreamType.VIDEO_ONLY:
                new_videos.append(info)
            elif info.stream_type == StreamType.AUDIO_ONLY:
                new_audios.append(info)
            elif info.stream_type == StreamType.MUXED:
                new_muxed.append(info)

        if new_videos or new_audios:
            self.pending_videos.extend(new_videos)
            self.pending_audios.extend(new_audios)

        if new_muxed:
            self.muxed_files.extend(new_muxed)

        # 智能重新匹配
        match_result = auto_match(self.all_stream_infos, self.root_paths)
        self.tasks = match_result.auto_tasks

        self._save_workspace_state()
        
        # 刷新前端
        tasks_json = json.dumps(self._get_queue_data()["tasks"], ensure_ascii=False)
        self._evaluate_js_safe(f"renderQueue({tasks_json})")

    def _get_queue_data(self) -> Dict:
        """生成前端渲染所需的规格数据"""
        tasks_list = []
        for i, t in enumerate(self.tasks):
            # 获取格式和大小
            fmt = self.settings.get("output_format", "mp4").upper()
            size_str = "未知"
            if os.path.exists(t.video_file):
                v_size = os.path.getsize(t.video_file)
                a_size = os.path.getsize(t.audio_file) if os.path.exists(t.audio_file) else 0
                size_str = f"{(v_size + a_size) / (1024*1024):.1f} MB"

            tasks_list.append({
                "name": t.output_name,
                "format": fmt,
                "resolution": "1080P" if "1080" in t.output_name else "自动识别",
                "size": size_str,
                "status": t.status,
                "error": t.error_message
            })
        return {"status": "success", "tasks": tasks_list}

    def _evaluate_js_safe(self, code: str):
        """线程安全地在 Webview window 中执行 JS"""
        if self.window:
            try:
                # pywebview 的 evaluate_js 是非阻塞的，可直接从子线程安全调用
                self.window.evaluate_js(code)
            except Exception as e:
                logger.debug(f"Evaluate JS failed (probably window closed): {e}")
