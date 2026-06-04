"""
批量处理器模块
支持一次导入多个文件夹，各自独立扫描匹配，统一管理批次任务
"""

import uuid
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from fisheep_video_merger.core.models import MergeTask, MatchResult
from fisheep_video_merger.core.scanner import scan_multiple_directories
from fisheep_video_merger.core.matcher import auto_match
from fisheep_video_merger.core.naming import apply_naming_template
from fisheep_video_merger.utils.logger import get_logger

logger = get_logger()

# 默认命名模板
DEFAULT_NAMING_TEMPLATE = "{series}_{ep}"


@dataclass
class Batch:
    """批量处理批次数据"""
    id: str
    folders: List[str]
    tasks: List[MergeTask] = field(default_factory=list)
    pending: int = 0          # 待合并数量（auto_tasks 数量）
    muxed: int = 0            # 已配对（含已混流文件）数量
    status: str = "created"   # created / scanning / scanned / failed
    naming_template: str = DEFAULT_NAMING_TEMPLATE
    series_name: str = ""


class BatchProcessor:
    """批量处理器，管理多个批次的创建、扫描、预览和执行"""

    def __init__(self) -> None:
        self._batches: Dict[str, Batch] = {}

    def create_batch(
        self,
        folders: List[str],
        series_name: str = "",
        naming_template: str = DEFAULT_NAMING_TEMPLATE,
    ) -> Batch:
        """
        创建新的处理批次

        Args:
            folders: 文件夹路径列表
            series_name: 系列名称
            naming_template: 命名模板

        Returns:
            新创建的 Batch 对象
        """
        batch_id = uuid.uuid4().hex[:8]
        batch = Batch(
            id=batch_id,
            folders=list(folders),
            naming_template=naming_template,
            series_name=series_name,
        )
        self._batches[batch_id] = batch
        logger.info(f"[Batch] 创建批次 {batch_id}，文件夹数: {len(folders)}")
        return batch

    def get_batch(self, batch_id: str) -> Optional[Batch]:
        """
        根据 ID 获取批次

        Args:
            batch_id: 批次 ID

        Returns:
            Batch 对象，不存在时返回 None
        """
        return self._batches.get(batch_id)

    def remove_batch(self, batch_id: str) -> bool:
        """
        删除指定批次

        Args:
            batch_id: 批次 ID

        Returns:
            删除成功返回 True，批次不存在返回 False
        """
        if batch_id in self._batches:
            del self._batches[batch_id]
            logger.info(f"[Batch] 删除批次 {batch_id}")
            return True
        logger.warning(f"[Batch] 尝试删除不存在的批次: {batch_id}")
        return False

    def scan_batch(self, batch_id: str) -> Optional[Batch]:
        """
        扫描批次内所有文件夹并自动配对

        逐个文件夹独立扫描，单个文件夹失败不阻塞其他文件夹。
        扫描结果汇总后统一调用 auto_match 进行配对。

        Args:
            batch_id: 批次 ID

        Returns:
            更新后的 Batch 对象，批次不存在时返回 None
        """
        batch = self._batches.get(batch_id)
        if batch is None:
            logger.warning(f"[Batch] 扫描失败，批次不存在: {batch_id}")
            return None

        batch.status = "scanning"
        logger.info(f"[Batch] 开始扫描批次 {batch_id}，共 {len(batch.folders)} 个文件夹")

        all_stream_infos = []
        scanned_roots: List[str] = []
        failed_folders: List[str] = []

        for folder in batch.folders:
            try:
                infos = scan_multiple_directories([folder])
                all_stream_infos.extend(infos)
                scanned_roots.append(folder)
                logger.info(
                    f"[Batch] 扫描文件夹完成: {folder}，"
                    f"发现 {len(infos)} 个流"
                )
            except Exception as e:
                failed_folders.append(folder)
                logger.error(f"[Batch] 扫描文件夹失败: {folder}，错误: {e}")

        # 汇总结果进行自动配对
        if all_stream_infos and scanned_roots:
            try:
                match_result: MatchResult = auto_match(all_stream_infos, scanned_roots)
                batch.tasks = match_result.auto_tasks
                batch.pending = len(match_result.pending_videos) + len(match_result.pending_audios)
                batch.muxed = len(match_result.muxed_files)
                batch.status = "scanned"
                logger.info(
                    f"[Batch] 批次 {batch_id} 扫描完成: "
                    f"配对任务 {len(batch.tasks)}，"
                    f"待处理 {batch.pending}，"
                    f"已混流 {batch.muxed}，"
                    f"失败文件夹 {len(failed_folders)}"
                )
            except Exception as e:
                batch.status = "failed"
                logger.error(f"[Batch] 批次 {batch_id} 自动配对失败: {e}")
        elif not all_stream_infos:
            batch.tasks = []
            batch.pending = 0
            batch.muxed = 0
            batch.status = "scanned"
            logger.warning(
                f"[Batch] 批次 {batch_id} 扫描完成但无有效流信息"
                f"（失败文件夹 {len(failed_folders)}）"
            )

        return batch

    def preview_names(self, batch_id: str, template: str) -> Optional[List[Dict[str, str]]]:
        """
        预览批次任务应用命名模板后的输出名称

        Args:
            batch_id: 批次 ID
            template: 命名模板字符串

        Returns:
            包含 task_index / output_name / video_file / audio_file 的字典列表，
            批次不存在时返回 None
        """
        batch = self._batches.get(batch_id)
        if batch is None:
            logger.warning(f"[Batch] 预览失败，批次不存在: {batch_id}")
            return None

        previews: List[Dict[str, str]] = []
        for idx, task in enumerate(batch.tasks):
            try:
                name = apply_naming_template(
                    template=template,
                    video_filepath=task.video_file,
                    source_dir=task.source_dir,
                    root_path=task.root_path,
                    index=idx,
                )
                previews.append({
                    "task_index": idx,
                    "output_name": name,
                    "video_file": task.video_file,
                    "audio_file": task.audio_file,
                })
            except Exception as e:
                logger.warning(f"[Batch] 预览命名失败 (任务 {idx}): {e}")
                previews.append({
                    "task_index": idx,
                    "output_name": task.output_name,
                    "video_file": task.video_file,
                    "audio_file": task.audio_file,
                })

        return previews
