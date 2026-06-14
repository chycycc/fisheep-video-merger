"""
文件导入服务
负责扫描文件夹、分析文件、匹配音视频对
设计原则：自治模块，通过 AppState 共享状态，不依赖 bridge 回调
"""

import os
import threading
from typing import List, Tuple
from concurrent.futures import ThreadPoolExecutor as TPE

from fisheep_video_merger.core.scanner import scan_multiple_directories, analyze_file, SUPPORTED_EXTENSIONS
from fisheep_video_merger.core.matcher import auto_match, apply_naming_template
from fisheep_video_merger.utils.ffprobe import StreamType
from fisheep_video_merger.utils.logger import get_logger

logger = get_logger()


class ImportService:
    """文件导入：扫描文件夹、分析文件、匹配音视频"""

    def __init__(self, app_state, lock: threading.Lock, task_mgr):
        """
        Args:
            app_state: AppState 实例，持有 root_paths/all_stream_infos/pending_*/muxed_files/settings
            lock: 线程锁
            task_mgr: TaskManagerService 实例
        """
        self._app_state = app_state
        self._lock = lock
        self._task_mgr = task_mgr

    def classify_paths(self, file_paths: List[str]) -> Tuple[List[str], List[str]]:
        """将路径分类为文件夹和媒体文件"""
        folders, media_files = [], []
        for path in file_paths:
            if os.path.isdir(path):
                folders.append(path)
            elif os.path.splitext(path)[1].lower() in SUPPORTED_EXTENSIONS:
                media_files.append(path)
        return folders, media_files

    def scan_folders(self, directories: List[str]) -> List[str]:
        """扫描文件夹，返回实际新增的目录列表"""
        new_directories = []
        for d in directories:
            d = os.path.abspath(d)
            if not os.path.isdir(d):
                continue
            if d not in self._app_state.root_paths:
                self._app_state.root_paths.append(d)
            new_directories.append(d)
        return new_directories

    def _apply_naming_template(self):
        """应用命名模板到所有任务"""
        template = (self._app_state.settings.get("naming_template") or "").strip()
        if not template:
            return
        for i, task in enumerate(self._task_mgr.tasks):
            task.output_name = apply_naming_template(
                template, task.video_file, task.source_dir, task.root_path, i
            )

    def _auto_save(self):
        """保存工作区状态"""
        self._app_state.save_debounced()

    def run_folder_scan(self, new_directories: List[str], on_complete=None):
        """异步扫描文件夹并匹配

        Args:
            on_complete: 回调函数 (queue_data: dict, has_results: bool) -> None
        """
        def worker():
            try:
                results = scan_multiple_directories(new_directories)
                if not results:
                    if on_complete:
                        on_complete(self._task_mgr.get_queue_view_model(
                            self._app_state.pending_videos, self._app_state.pending_audios,
                            self._app_state.muxed_files, self._app_state.settings
                        ), False)
                    return

                with self._lock:
                    existing = {x.filepath for x in self._app_state.all_stream_infos}
                    for info in results:
                        if info.filepath not in existing:
                            self._app_state.all_stream_infos.append(info)

                    match_result = auto_match(self._app_state.all_stream_infos, self._app_state.root_paths)
                    self._task_mgr.preserve_status(match_result.auto_tasks)
                    self._app_state.pending_videos = match_result.pending_videos
                    self._app_state.pending_audios = match_result.pending_audios
                    self._apply_naming_template()

                    if match_result.muxed_files:
                        for m in match_result.muxed_files:
                            if not any(x.filepath == m.filepath for x in self._app_state.muxed_files):
                                self._app_state.muxed_files.append(m)

                if not self._app_state.settings.get("output_dir"):
                    if self._app_state.root_paths:
                        self._app_state.settings['output_dir'] = os.path.dirname(self._app_state.root_paths[0])

                self._auto_save()

                has_results = bool(match_result.auto_tasks or match_result.pending_videos)
                if on_complete:
                    on_complete(self._task_mgr.get_queue_view_model(
                        self._app_state.pending_videos, self._app_state.pending_audios,
                        self._app_state.muxed_files, self._app_state.settings
                    ), has_results)

            except Exception as e:
                logger.error(f"异步扫描失败: {e}")
                if on_complete:
                    on_complete({"status": "error", "message": str(e)}, False)

        threading.Thread(target=worker, daemon=True).start()

    def run_file_import(self, filepaths: List[str], on_complete=None):
        """异步分析文件并匹配

        Args:
            on_complete: 回调函数 (queue_data: dict, new_videos: list, new_audios: list, new_muxed: list) -> None
        """
        def worker():
            try:
                existing = {x.filepath for x in self._app_state.all_stream_infos}
                new_fps = [
                    fp for fp in filepaths
                    if os.path.splitext(fp)[1].lower() in SUPPORTED_EXTENSIONS
                    and fp not in existing
                ]
                if not new_fps:
                    return

                with TPE(max_workers=4) as pool:
                    results = list(pool.map(analyze_file, new_fps))

                new_videos, new_audios, new_muxed = [], [], []
                with self._lock:
                    for info in results:
                        self._app_state.all_stream_infos.append(info)
                        if info.stream_type == StreamType.VIDEO_ONLY:
                            new_videos.append(info)
                        elif info.stream_type == StreamType.AUDIO_ONLY:
                            new_audios.append(info)
                        elif info.stream_type == StreamType.MUXED:
                            new_muxed.append(info)

                with self._lock:
                    match_result = auto_match(self._app_state.all_stream_infos, self._app_state.root_paths)
                    self._task_mgr.preserve_status(match_result.auto_tasks)
                    self._app_state.pending_videos = match_result.pending_videos
                    self._app_state.pending_audios = match_result.pending_audios
                    self._apply_naming_template()

                    if new_muxed:
                        for m in new_muxed:
                            if not any(x.filepath == m.filepath for x in self._app_state.muxed_files):
                                self._app_state.muxed_files.append(m)

                    self._auto_save()

                if on_complete:
                    on_complete(
                        self._task_mgr.get_queue_view_model(
                            self._app_state.pending_videos, self._app_state.pending_audios,
                            self._app_state.muxed_files, self._app_state.settings
                        ),
                        new_videos, new_audios, new_muxed
                    )

            except Exception as e:
                logger.error(f"添加文件失败: {e}")
                if on_complete:
                    on_complete({"status": "error", "message": str(e)}, [], [], [])

        threading.Thread(target=worker, daemon=True).start()
