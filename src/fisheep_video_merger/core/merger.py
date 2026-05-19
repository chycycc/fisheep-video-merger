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


def build_remux_command(
    input_file: str,
    output_path: str,
) -> list[str]:
    """
    构建 ffmpeg 转封装命令（不改编码，仅换容器格式）

    Args:
        input_file: 输入文件路径
        output_path: 输出文件路径

    Returns:
        ffmpeg 命令参数列表
    """
    return [
        get_ffmpeg_path(),
        "-i", input_file,
        "-c", "copy",
        "-map", "0",
        "-y",
        output_path,
    ]


def _run_ffmpeg_with_progress(
    cmd: list[str],
    output_path: str,
    progress_callback: Optional[Callable[[str], None]],
    op_name: str = "合并",
) -> tuple[bool, Optional[str]]:
    """
    在后台运行 ffmpeg 并实时解析输出生成带百分比的进度

    Args:
        cmd: ffmpeg 命令参数列表
        output_path: 输出路径
        progress_callback: 进度回调
        op_name: 操作名称，如 "合并" 或 "转封装"

    Returns:
        (成功标志, 错误信息)
    """
    import re
    filename = os.path.basename(output_path)
    # 正则表达式匹配 Duration 和 time= 进度
    duration_regex = re.compile(r"Duration:\s*(\d{2}):(\d{2}):(\d{2})\.(\d{2})")
    time_regex = re.compile(r"time=\s*(\d{2}):(\d{2}):(\d{2})\.(\d{2})")

    def to_seconds(match) -> float:
        h, m, s, ms = match.groups()
        return int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 100.0

    total_seconds = 0.0
    full_stderr = []
    
    # 进度防抖节流锁 (C-3.1.2)
    import time
    last_emit_time = 0.0
    last_pct = -1.0

    logger.info(f"开始执行 ffmpeg {op_name}: {' '.join(cmd)}")
    try:
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            shell=False,
            text=True,
            encoding="utf-8",
            errors="replace",
        )

        # 逐字符读取以正确捕获 \r 字符（ffmpeg 进度输出）
        buffer = ""
        while True:
            char = process.stderr.read(1)
            if not char:
                break
            if char in ("\r", "\n"):
                line = buffer.strip()
                buffer = ""
                if not line:
                    continue
                
                full_stderr.append(line)

                # 1. 从最初的控制台流信息中匹配视频/音频时长
                if total_seconds == 0.0:
                    dur_match = duration_regex.search(line)
                    if dur_match:
                        total_seconds = to_seconds(dur_match)

                # 2. 实时流复制进程中解析 time=，推送百分比进度
                if total_seconds > 0.0:
                    t_match = time_regex.search(line)
                    if t_match:
                        curr = to_seconds(t_match)
                        pct = min(99.9, (curr / total_seconds) * 100.0)
                        now = time.time()
                        # 节流条件：百分比变动幅度大于 1%，或距离上次发送超过 150ms，或到达临界点
                        if (now - last_emit_time > 0.15) or (abs(pct - last_pct) >= 1.0) or pct >= 99.9:
                            if progress_callback:
                                progress_callback(f"正在{op_name}: {filename} ({pct:.1f}%)")
                            last_emit_time = now
                            last_pct = pct
            else:
                buffer += char

        # 等待进程优雅退出
        process.wait(timeout=30)
        
        if process.returncode == 0:
            logger.info(f"{op_name}成功: {output_path}")
            return True, None
        else:
            # 回退几行 stderr 寻找具体的 FFmpeg 错误反馈
            tail = "\n".join(full_stderr[-5:])
            logger.error(f"{op_name}失败: {output_path}\n{tail}")
            return False, tail[:500]

    except subprocess.TimeoutExpired:
        try:
            process.kill()
        except:
            pass
        return False, "ffmpeg 进程执行超时"
    except Exception as e:
        logger.error(f"{op_name}执行时发生异常: {e}")
        return False, str(e)


def remux_single(
    input_file: str,
    output_path: str,
    progress_callback: Optional[Callable[[str], None]] = None,
) -> tuple[bool, Optional[str]]:
    """
    执行单个 muxed 文件的转封装

    Args:
        input_file: 输入文件路径
        output_path: 输出文件路径
        progress_callback: 进度回调

    Returns:
        (成功标志, 错误信息)
    """
    output_dir = os.path.dirname(output_path)
    try:
        os.makedirs(output_dir, exist_ok=True)
    except OSError as e:
        return False, f"创建输出目录失败: {e}"

    cmd = build_remux_command(input_file, output_path)
    
    if progress_callback:
        progress_callback(f"正在准备转封装: {os.path.basename(output_path)}")

    return _run_ffmpeg_with_progress(cmd, output_path, progress_callback, "转封装")


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
    output_dir = os.path.dirname(output_path)
    try:
        os.makedirs(output_dir, exist_ok=True)
    except OSError as e:
        return False, f"创建输出目录失败: {e}"

    cmd = build_ffmpeg_command(video_file, audio_file, output_path)

    if progress_callback:
        progress_callback(f"正在准备合并: {os.path.basename(output_path)}")

    return _run_ffmpeg_with_progress(cmd, output_path, progress_callback, "合并")


import threading

try:
    from PySide6.QtCore import QRunnable, QObject, Signal
    HAS_PYSIDE = True
except ImportError:
    HAS_PYSIDE = False

if HAS_PYSIDE:
    class MergeWorkerSignals(QObject):
        """合并 Worker 线程信号"""
        progress = Signal(int, str)           # (task_index, progress_text)
        finished = Signal(int, object)        # (task_index, MergeResult)
        error = Signal(int, str)              # (task_index, error_msg)
        conflict_requested = Signal(int, str)  # (task_index, expected_output_path)


    class MergeWorker(QRunnable):
        """并发合并工作项"""

        def __init__(
            self,
            task_index: int,
            video_file: Optional[str],
            audio_file: Optional[str],
            output_path: str,
            is_muxed: bool = False,
        ):
            super().__init__()
            self.task_index = task_index
            self.video_file = video_file
            self.audio_file = audio_file
            self.output_path = output_path
            self.is_muxed = is_muxed
            
            self.signals = MergeWorkerSignals()
            
            # 用于挂起线程等待主线程重名决策的 Event (C-2)
            self.conflict_resolved_event = threading.Event()
            self.resolved_strategy: Optional[ConflictStrategy] = None
            self.resolved_applied_all = False
            self.resolved_path: Optional[str] = None

        def run(self):
            """执行合并/转封装"""
            try:
                actual_output_path = self.output_path
                
                # 1. 检查是否存在目标文件（若存在，触发重名冲突询问）
                if os.path.exists(self.output_path):
                    # 发射冲突信号给主线程
                    self.signals.conflict_requested.emit(self.task_index, self.output_path)
                    
                    # 阻塞挂起子线程，等待主线程做决策 (C-2)
                    self.conflict_resolved_event.wait()
                    
                    # 决策完成，获取结果
                    if self.resolved_strategy == ConflictStrategy.SKIP:
                        logger.info(f"任务 {self.task_index}：用户选择跳过")
                        result = MergeResult(
                            task_index=self.task_index,
                            output_name=os.path.basename(self.output_path),
                            output_path=self.output_path,
                            success=True,
                            error_message="用户选择跳过",
                            actual_path=self.output_path,
                        )
                        self.signals.finished.emit(self.task_index, result)
                        return
                    
                    if self.resolved_path:
                        actual_output_path = self.resolved_path

                # 2. 执行合并或转封装
                if self.is_muxed:
                    # 转封装操作
                    success, err = remux_single(
                        self.video_file,  # 对于 muxed, video_file 就是 input_file
                        actual_output_path,
                        progress_callback=lambda txt: self.signals.progress.emit(self.task_index, txt)
                    )
                else:
                    # 合并操作
                    success, err = merge_single(
                        self.video_file,
                        self.audio_file,
                        actual_output_path,
                        progress_callback=lambda txt: self.signals.progress.emit(self.task_index, txt)
                    )
                    
                result = MergeResult(
                    task_index=self.task_index,
                    output_name=os.path.basename(actual_output_path),
                    output_path=self.output_path,
                    success=success,
                    error_message=err,
                    actual_path=actual_output_path,
                )
                
                if success:
                    self.signals.finished.emit(self.task_index, result)
                else:
                    self.signals.error.emit(self.task_index, err or "未知合并错误")
                    
            except Exception as e:
                logger.error(f"MergeWorker 发生未捕获异常: {e}")
                self.signals.error.emit(self.task_index, str(e))


