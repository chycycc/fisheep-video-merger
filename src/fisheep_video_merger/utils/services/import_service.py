"""
文件导入服务
负责扫描文件夹、分析文件、匹配音视频对
"""

import os
import threading
from typing import List, Callable, Dict
from concurrent.futures import ThreadPoolExecutor as TPE

from fisheep_video_merger.core.scanner import scan_multiple_directories, analyze_file, SUPPORTED_EXTENSIONS
from fisheep_video_merger.core.matcher import auto_match
from fisheep_video_merger.utils.ffprobe import StreamType
from fisheep_video_merger.utils.logger import get_logger

logger = get_logger()


class ImportService:
    """文件导入：扫描文件夹、分析文件、匹配音视频"""

    def __init__(self, state: dict, lock: threading.Lock, task_mgr,
                 apply_naming_template: Callable, save_state: Callable,
                 get_queue_data: Callable, send_message: Callable):
        self._state = state  # 共享状态 dict: root_paths, all_stream_infos, pending_*, muxed_files, settings
        self._lock = lock
        self._task_mgr = task_mgr
        self._apply_naming_template = apply_naming_template
        self._save_state = save_state
        self._get_queue_data = get_queue_data
        self._send_message = send_message

    def classify_paths(self, file_paths: List[str]) -> tuple:
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
            if d not in self._state['root_paths']:
                self._state['root_paths'].append(d)
            new_directories.append(d)
        return new_directories

    def run_folder_scan(self, new_directories: List[str]):
        """异步扫描文件夹并匹配"""
        def worker():
            try:
                results = scan_multiple_directories(new_directories)
                if not results:
                    return
                with self._lock:
                    existing = {x.filepath for x in self._state['all_stream_infos']}
                    for info in results:
                        if info.filepath not in existing:
                            self._state['all_stream_infos'].append(info)

                    match_result = auto_match(self._state['all_stream_infos'], self._state['root_paths'])
                    self._task_mgr.preserve_status(match_result.auto_tasks)
                    self._state['pending_videos'] = match_result.pending_videos
                    self._state['pending_audios'] = match_result.pending_audios
                    self._apply_naming_template()

                    if match_result.muxed_files:
                        for m in match_result.muxed_files:
                            if not any(x.filepath == m.filepath for x in self._state['muxed_files']):
                                self._state['muxed_files'].append(m)

                if not self._state['settings'].get("output_dir"):
                    if self._state['root_paths']:
                        self._state['settings']['output_dir'] = os.path.dirname(self._state['root_paths'][0])

                self._save_state()
                self._send_message("state_update", self._get_queue_data())

                if match_result.auto_tasks or match_result.pending_videos:
                    self._send_message("toast", {"message": "文件夹扫描完成", "type": "success"})
                else:
                    self._send_message("toast", {"message": "选中文件夹内未发现支持的视频缓存", "type": "warning"})
            except Exception as e:
                logger.error(f"异步扫描失败: {e}")
                self._send_message("toast", {"message": f"扫描失败: {e}", "type": "error"})

        threading.Thread(target=worker, daemon=True).start()

    def run_file_import(self, filepaths: List[str]):
        """异步分析文件并匹配"""
        def worker():
            try:
                existing = {x.filepath for x in self._state['all_stream_infos']}
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
                        self._state['all_stream_infos'].append(info)
                        if info.stream_type == StreamType.VIDEO_ONLY:
                            new_videos.append(info)
                        elif info.stream_type == StreamType.AUDIO_ONLY:
                            new_audios.append(info)
                        elif info.stream_type == StreamType.MUXED:
                            new_muxed.append(info)

                with self._lock:
                    old_tasks_count = len(self._task_mgr.tasks)
                    match_result = auto_match(self._state['all_stream_infos'], self._state['root_paths'])
                    self._task_mgr.preserve_status(match_result.auto_tasks)
                    self._state['pending_videos'] = match_result.pending_videos
                    self._state['pending_audios'] = match_result.pending_audios
                    self._apply_naming_template()

                    if new_muxed:
                        for m in new_muxed:
                            if not any(x.filepath == m.filepath for x in self._state['muxed_files']):
                                self._state['muxed_files'].append(m)

                    self._save_state()

                self._send_message("state_update", self._get_queue_data())

                if new_videos or new_audios:
                    if len(self._task_mgr.tasks) <= old_tasks_count:
                        self._send_message("toast", {"message": "导入的片段由于缺少对应音/视频，已自动归入【待整理】队列", "type": "warning"})
                elif new_muxed:
                    self._send_message("toast", {"message": "导入的视频已是完整文件，自动归入【已完整】队列", "type": "info"})
            except Exception as e:
                logger.error(f"添加文件失败: {e}")
                self._send_message("toast", {"message": f"添加文件失败: {e}", "type": "error"})

        threading.Thread(target=worker, daemon=True).start()
