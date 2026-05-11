"""
合并引擎模块
负责调用 ffmpeg 执行合并操作
"""

import os
import subprocess
from enum import Enum
from typing import Callable, Optional

from fisheep_video_merger.utils.logger import get_logger

logger = get_logger()


class ConflictStrategy(Enum):
    """重名处理策略"""
    OVERWRITE = "overwrite"
    RENAME = "rename"
    SKIP = "skip"


class MergeResult:
    """单个任务的合并结果"""

    def __init__(
        self,
        task_index: int,
        output_name: str,
        output_path: str,
        success: bool,
        error_message: Optional[str] = None,
        actual_path: Optional[str] = None,
    ):
        self.task_index = task_index
        self.output_name = output_name
        self.output_path = output_path
        self.success = success
        self.error_message = error_message
        self.actual_path = actual_path or output_path


def get_ffmpeg_path() -> str:
    """获取 ffmpeg 可执行文件路径"""
    return "ffmpeg"


def build_ffmpeg_command(
    video_file: str,
    audio_file: str,
    output_path: str,
) -> list[str]:
    """
    构建 ffmpeg 合并命令

    使用流复制模式，保留原始质量。

    Args:
        video_file: 视频文件路径
        audio_file: 音频文件路径
        output_path: 输出文件路径

    Returns:
        ffmpeg 命令参数列表
    """
    return [
        get_ffmpeg_path(),
        "-i", video_file,
        "-i", audio_file,
        "-c", "copy",
        "-map", "0:v:0",
        "-map", "1:a:0",
        "-y",  # 默认覆盖，由上层处理重名策略
        output_path,
    ]


def handle_conflict(
    output_path: str,
    strategy: ConflictStrategy,
    applied_all: bool,
    conflict_callback: Optional[Callable[[str], tuple[ConflictStrategy, bool]]] = None,
) -> tuple[str, ConflictStrategy, bool]:
    """
    处理输出文件重名冲突

    Args:
        output_path: 原始输出路径
        strategy: 当前策略
        applied_all: 是否已应用到全部
        conflict_callback: 冲突回调，接收输出路径，返回 (策略, 应用到全部)

    Returns:
        (实际输出路径, 使用的策略, 是否应用到全部)
    """
    if not os.path.exists(output_path):
        return output_path, strategy, applied_all

    if strategy == ConflictStrategy.OVERWRITE:
        return output_path, strategy, applied_all

    if strategy == ConflictStrategy.SKIP:
        return output_path, strategy, applied_all

    if strategy == ConflictStrategy.RENAME:
        base, ext = os.path.splitext(output_path)
        counter = 1
        while True:
            new_path = f"{base}_{counter}{ext}"
            if not os.path.exists(new_path):
                return new_path, strategy, applied_all
            counter += 1

    # 需要用户决策
    if conflict_callback:
        strategy, applied_all = conflict_callback(output_path)
        if strategy == ConflictStrategy.RENAME:
            base, ext = os.path.splitext(output_path)
            counter = 1
            while True:
                new_path = f"{base}_{counter}{ext}"
                if not os.path.exists(new_path):
                    return new_path, strategy, applied_all
                counter += 1
        return output_path, strategy, applied_all

    # 默认覆盖
    return output_path, ConflictStrategy.OVERWRITE, False


def merge_single(
    video_file: str,
    audio_file: str,
    output_path: str,
    progress_callback: Optional[Callable[[str], None]] = None,
) -> tuple[bool, Optional[str]]:
    """
    执行单个合并任务

    Args:
        video_file: 视频文件路径
        audio_file: 音频文件路径
        output_path: 输出文件路径
        progress_callback: 进度回调，传入当前状态文本

    Returns:
        (成功标志, 错误信息)
    """
    # 创建输出目录
    output_dir = os.path.dirname(output_path)
    try:
        os.makedirs(output_dir, exist_ok=True)
    except OSError as e:
        return False, f"创建输出目录失败: {e}"

    # 构建命令
    cmd = build_ffmpeg_command(video_file, audio_file, output_path)

    if progress_callback:
        progress_callback(f"正在合并: {os.path.basename(output_path)}")

    logger.info(f"执行 ffmpeg: {' '.join(cmd)}")

    try:
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            shell=False,
        )
        _, stderr = process.communicate(timeout=3600)  # 1小时超时

        if process.returncode == 0:
            logger.info(f"合并成功: {output_path}")
            return True, None
        else:
            error_msg = stderr.decode("utf-8", errors="replace")[:500]
            logger.error(f"合并失败: {output_path} - {error_msg}")
            return False, error_msg

    except subprocess.TimeoutExpired:
        process.kill()
        msg = "ffmpeg 执行超时（超过1小时）"
        logger.error(msg)
        return False, msg
    except Exception as e:
        logger.error(f"合并异常: {e}")
        return False, str(e)


def merge_all(
    tasks: list[dict],
    conflict_callback: Optional[Callable[[str], tuple[ConflictStrategy, bool]]] = None,
    progress_callback: Optional[Callable[[int, int, str], None]] = None,
    task_status_callback: Optional[Callable[[int, bool, Optional[str]], None]] = None,
) -> list[MergeResult]:
    """
    批量执行合并任务

    Args:
        tasks: 任务列表，每个任务为字典，包含:
            - video_file: 视频路径
            - audio_file: 音频路径
            - output_path: 输出路径
            - output_name: 输出文件名
        conflict_callback: 重名冲突回调
        progress_callback: 进度回调 (当前序号, 总数, 状态文本)
        task_status_callback: 任务状态回调 (索引, 成功标志, 错误信息)

    Returns:
        合并结果列表
    """
    results: list[MergeResult] = []
    total = len(tasks)
    conflict_strategy = ConflictStrategy.OVERWRITE
    applied_all = False

    for i, task in enumerate(tasks):
        video_file = task["video_file"]
        audio_file = task["audio_file"]
        output_path = task["output_path"]
        output_name = task.get("output_name", os.path.basename(output_path))

        if progress_callback:
            progress_callback(i + 1, total, f"正在合并: {output_name}")

        # 处理重名冲突
        if os.path.exists(output_path) and not applied_all:
            actual_path, conflict_strategy, applied_all = handle_conflict(
                output_path, conflict_strategy, applied_all, conflict_callback,
            )
        elif os.path.exists(output_path) and applied_all:
            if conflict_strategy == ConflictStrategy.SKIP:
                results.append(MergeResult(
                    task_index=i,
                    output_name=output_name,
                    output_path=output_path,
                    success=False,
                    error_message="已跳过（文件已存在）",
                ))
                if task_status_callback:
                    task_status_callback(i, False, "已跳过（文件已存在）")
                continue
            elif conflict_strategy == ConflictStrategy.RENAME:
                base, ext = os.path.splitext(output_path)
                counter = 1
                while True:
                    new_path = f"{base}_{counter}{ext}"
                    if not os.path.exists(new_path):
                        output_path = new_path
                        break
                    counter += 1
        else:
            actual_path = output_path

        # 执行合并
        success, error = merge_single(
            video_file, audio_file, actual_path,
            progress_callback=lambda s: progress_callback(
                i + 1, total, s
            ) if progress_callback else None,
        )

        result = MergeResult(
            task_index=i,
            output_name=output_name,
            output_path=actual_path,
            success=success,
            error_message=error,
        )
        results.append(result)

        if task_status_callback:
            task_status_callback(i, success, error)

    return results
