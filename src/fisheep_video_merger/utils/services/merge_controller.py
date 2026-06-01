"""
合并控制器服务
负责多线程合并调度、FFmpeg 进程管理、取消机制
"""

import os
import re
import json
import threading
from typing import Dict, Optional, Callable
from concurrent.futures import ThreadPoolExecutor, CancelledError

from fisheep_video_merger.core.merger import merge_single
from fisheep_video_merger.utils.logger import get_logger

logger = get_logger()


class MergeControllerService:
    """多线程合并控制器"""

    def __init__(self):
        self.is_merging = False
        self._cancel_event = threading.Event()
        self._executor: Optional[ThreadPoolExecutor] = None
        self._futures = []
        self._active_processes: Dict[int, object] = {}

    def start_merge(self, tasks, concurrency: int, settings: Dict,
                    task_manager, progress_callback: Callable,
                    status_callback: Callable, done_callback: Callable):
        """
        启动合并任务

        Args:
            tasks: 任务列表
            concurrency: 并发数
            settings: 设置字典
            task_manager: TaskManagerService 实例
            progress_callback: fn(index, percent, eta, speed)
            status_callback: fn(index, status, error)
            done_callback: fn(completed, failed)
        """
        if self.is_merging:
            return

        self.is_merging = True
        self._cancel_event.clear()
        self._active_processes.clear()

        pending_indexes = task_manager.get_pending_indexes()
        if not pending_indexes:
            self.is_merging = False
            done_callback(0, 0)
            return

        def merge_worker(index, task):
            """单个合并任务的工作函数"""
            output_dir = settings.get("output_dir") or task.source_dir
            output_format = settings.get("output_format", "mp4")

            # 路径镜像
            path_depth = settings.get("path_depth", 0)
            if path_depth > 0 and task.root_path:
                try:
                    rel = os.path.relpath(task.source_dir, task.root_path)
                    parts = [p for p in rel.split(os.sep) if p not in ("..", ".", "")]
                    if parts:
                        mirror_parts = parts[:path_depth]
                        output_dir = os.path.join(output_dir, *mirror_parts)
                        os.makedirs(output_dir, exist_ok=True)
                except ValueError:
                    pass

            output_filename = f"{task.output_name}.{output_format}"
            output_path = os.path.join(output_dir, output_filename)

            # 处理冲突
            if os.path.exists(output_path):
                if not settings.get("overwrite", True):
                    base, ext = os.path.splitext(output_path)
                    counter = 1
                    while counter < 10000:
                        new_path = f"{base}_{counter}{ext}"
                        if not os.path.exists(new_path):
                            output_path = new_path
                            break
                        counter += 1

            # 进度回调
            def on_progress(txt):
                match = re.search(r"\((\d+(?:\.\d+)?)%\)", txt)
                percent = float(match.group(1)) if match else 0.0
                progress_callback(index, percent, "计算中...", "⚡")

            def on_process(process):
                self._active_processes[index] = process

            success, err = merge_single(
                task.video_file, task.audio_file, output_path,
                progress_callback=on_progress,
                process_callback=on_process
            )

            self._active_processes.pop(index, None)
            return index, success, err, output_path

        def run_loop():
            completed = 0
            failed = 0

            with ThreadPoolExecutor(max_workers=concurrency) as executor:
                self._executor = executor
                futures = []

                for idx in pending_indexes:
                    if self._cancel_event.is_set():
                        break
                    task_manager.update_task_status(idx, "processing")
                    status_callback(idx, "processing", None)
                    future = executor.submit(merge_worker, idx, task_manager.tasks[idx])
                    futures.append(future)

                for f in futures:
                    if self._cancel_event.is_set():
                        break
                    try:
                        index, success, err, output_path = f.result()
                        if success:
                            task_manager.update_task_status(index, "completed", None, output_path)
                            status_callback(index, "completed", None, output_path)
                            completed += 1
                        else:
                            task_manager.update_task_status(index, "failed", err)
                            status_callback(index, "failed", err)
                            failed += 1
                    except CancelledError:
                        pass

            self._executor = None
            self.is_merging = False
            done_callback(completed, failed)

        thread = threading.Thread(target=run_loop, daemon=True)
        thread.start()

    def cancel_merge(self):
        """取消所有正在运行的合并任务"""
        if not self.is_merging:
            return
        self._cancel_event.set()
        for idx, process in list(self._active_processes.items()):
            try:
                process.kill()
            except Exception:
                pass
        self._active_processes.clear()
        if self._executor:
            self._executor.shutdown(wait=False, cancel_futures=True)

    def get_merge_estimate(self, tasks, concurrency: int, settings: Dict) -> Dict:
        """预估合并耗时"""
        total_size = 0
        pending_count = 0
        for t in tasks:
            if t.status != "completed":
                pending_count += 1
                for f in [t.video_file, t.audio_file]:
                    if f and os.path.exists(f):
                        total_size += os.path.getsize(f)

        if pending_count == 0:
            return {"estimate": "无待合并任务", "seconds": 0}

        speed_mbps = 500  # 流复制速度 MB/s
        estimated_sec = (total_size / (1024 * 1024)) / speed_mbps * 60 / concurrency

        if estimated_sec < 60:
            time_str = f"约 {max(1, int(estimated_sec))} 秒"
        else:
            time_str = f"约 {int(estimated_sec // 60)} 分 {int(estimated_sec % 60)} 秒"

        return {
            "estimate": time_str,
            "seconds": int(estimated_sec),
            "tasks": pending_count,
            "size_mb": round(total_size / (1024 * 1024), 1)
        }
