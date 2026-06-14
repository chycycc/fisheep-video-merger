"""
任务管理服务
负责合并任务的 CRUD 操作（增删改查、排序、重命名）和视图模型构建
"""

import os
import time
from typing import Dict, List

from fisheep_video_merger.core.matcher import MergeTask
from fisheep_video_merger.utils.logger import get_logger

logger = get_logger()


class TaskManagerService:
    """合并任务管理"""

    def __init__(self):
        self.tasks: List[MergeTask] = []

    def add_task(self, task: MergeTask) -> None:
        """添加单个任务到队列"""
        self.tasks.append(task)

    def rename_task(self, index: int, new_name: str) -> bool:
        """重命名任务输出文件名"""
        if 0 <= index < len(self.tasks):
            self.tasks[index].output_name = new_name
            return True
        return False

    def reset_task(self, index: int) -> bool:
        if 0 <= index < len(self.tasks):
            self.tasks[index].status = "pending"
            self.tasks[index].percent = 0
            self.tasks[index].error_message = None
            return True
        return False

    def batch_rename(self, indexes: List[int], prefix: str = "", suffix: str = "",
                     replace_from: str = "", replace_to: str = "") -> int:
        """批量重命名，返回成功数"""
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
        return count

    def reorder_tasks(self, from_idx: int, to_idx: int) -> bool:
        """调整任务顺序"""
        if 0 <= from_idx < len(self.tasks) and 0 <= to_idx < len(self.tasks):
            task = self.tasks.pop(from_idx)
            self.tasks.insert(to_idx, task)
            return True
        return False

    def update_task_status(self, index: int, status: str, error_message: str = None, output_path: str = None) -> bool:
        """更新任务状态"""
        if 0 <= index < len(self.tasks):
            self.tasks[index].status = status
            self.tasks[index].error_message = error_message
            if output_path is not None:
                self.tasks[index].output_path = output_path
            return True
        return False

    def delete_task(self, index: int) -> bool:
        """删除任务"""
        if 0 <= index < len(self.tasks):
            self.tasks.pop(index)
            return True
        return False

    def clear_completed(self) -> int:
        """清除已完成的任务，返回清除数"""
        before = len(self.tasks)
        self.tasks = [t for t in self.tasks if t.status != "completed"]
        return before - len(self.tasks)

    def clear_all(self) -> int:
        """清除所有任务，返回清除数"""
        count = len(self.tasks)
        self.tasks.clear()
        return count

    def get_pending_indexes(self) -> List[int]:
        """获取未完成任务的索引列表"""
        return [i for i, t in enumerate(self.tasks) if t.status != "completed"]

    def serialize_tasks(self) -> List[Dict]:
        """序列化任务列表为 JSON 兼容格式"""
        return [
            {
                "output_name": t.output_name,
                "video_file": t.video_file,
                "audio_file": t.audio_file,
                "source_dir": t.source_dir,
                "root_path": t.root_path,
                "status": t.status,
                "error_message": t.error_message,
                "is_multi_episode": t.is_multi_episode,
                "output_path": getattr(t, "output_path", None),
            }
            for t in self.tasks
        ]

    def deserialize_tasks(self, tasks_data: List[Dict]) -> List[MergeTask]:
        """从 JSON 数据反序列化任务列表"""
        tasks = []
        for t in tasks_data:
            try:
                tasks.append(MergeTask(
                    output_name=t.get("output_name", ""),
                    video_file=t.get("video_file", ""),
                    audio_file=t.get("audio_file", ""),
                    source_dir=t.get("source_dir", ""),
                    root_path=t.get("root_path", ""),
                    status=t.get("status", "pending"),
                    error_message=t.get("error_message"),
                    is_multi_episode=bool(t.get("is_multi_episode", False)),
                    output_path=t.get("output_path"),
                ))
            except Exception:
                continue
        return tasks

    def preserve_status(self, new_tasks: List[MergeTask]):
        """保留已完成/失败任务的状态（用于重新扫描后恢复状态）"""
        old_status = {}
        for t in self.tasks:
            if t.status in ("completed", "failed"):
                key = (t.video_file, t.audio_file)
                old_status[key] = (t.status, t.error_message, getattr(t, "output_path", None))

        for new_task in new_tasks:
            key = (new_task.video_file, new_task.audio_file)
            if key in old_status:
                new_task.status, new_task.error_message = old_status[key][:2]
                if len(old_status[key]) > 2:
                    new_task.output_path = old_status[key][2]

        self.tasks = new_tasks

    @staticmethod
    def _file_stat(filepath):
        """获取文件大小和修改时间"""
        size_str = mtime_str = "未知"
        if os.path.exists(filepath):
            stat = os.stat(filepath)
            size_str = f"{stat.st_size / (1024*1024):.1f} MB"
            mtime_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(stat.st_mtime))
        return size_str, mtime_str

    def get_queue_view_model(self, pending_videos, pending_audios, muxed_files, settings) -> Dict:
        """构建前端渲染所需的队列视图模型"""
        fmt = (settings.get("output_format") or "mp4").upper()

        tasks_list = []
        for t in self.tasks:
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
        for info in (pending_videos + pending_audios):
            size_str, mtime_str = self._file_stat(info.filepath)
            pending_list.append({
                "filepath": info.filepath,
                "name": os.path.basename(info.filepath),
                "size": size_str,
                "mtime": mtime_str,
                "stream_type": info.stream_type.value,
            })

        muxed_list = []
        for info in muxed_files:
            size_str, mtime_str = self._file_stat(info.filepath)
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
