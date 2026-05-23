"""
文件扫描模块
负责递归扫描目录收集 .m4s 文件，并调用 ffprobe 分析流类型
"""

import os
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable, Optional, List, Dict

from fisheep_video_merger.utils.ffprobe import StreamInfo, StreamType, analyze_file
from fisheep_video_merger.utils.logger import get_logger

logger = get_logger()


def scan_multiple_directories(
    root_paths: List[str],
    progress_callback: Optional[Callable[[int, int], None]] = None,
    dir_finished_callback: Optional[Callable[[str, List[StreamInfo]], None]] = None,
    max_workers: int = 4,
) -> List[StreamInfo]:
    """
    扫描多个目录，支持并行文件分析，并在每个子文件夹下的所有文件分析完成时进行增量回调。
    采用扁平化单级线程池设计，避免嵌套线程池导致的线程饥饿和资源过度消耗。

    Args:
        root_paths: 根目录路径列表
        progress_callback: 进度回调，参数 (全局已完成数, 全局总数)
        dir_finished_callback: 单目录所有文件扫描分析完成的回调，参数 (目录路径, 该目录下的 StreamInfo 列表)
        max_workers: 最大并发分析线程数

    Returns:
        合并后的 StreamInfo 列表
    """
    dir_to_files: Dict[str, List[str]] = {}
    flat_files: List[str] = []
    
    # 1. 递归收集所有符合条件的待分析文件，并建立目录到文件的映射
    for root_path in root_paths:
        root_path = os.path.abspath(root_path)
        if not os.path.exists(root_path):
            logger.warning(f"扫描路径不存在: {root_path}")
            continue
        
        # 兼容单文件输入模式
        if os.path.isfile(root_path):
            if root_path.lower().endswith(".m4s"):
                dirpath = os.path.dirname(root_path)
                dir_to_files.setdefault(dirpath, []).append(root_path)
                flat_files.append(root_path)
            continue

        for dirpath, _, filenames in os.walk(root_path):
            m4s_in_dir = [
                os.path.join(dirpath, f)
                for f in filenames
                if f.lower().endswith(".m4s")
            ]
            if m4s_in_dir:
                dir_to_files.setdefault(dirpath, []).extend(m4s_in_dir)
                flat_files.extend(m4s_in_dir)

    total_files = len(flat_files)
    if progress_callback:
        progress_callback(0, total_files)

    if not flat_files:
        logger.info("未在给定路径中找到任何 .m4s 缓存文件")
        # 触发空的回调以防万一
        if dir_finished_callback:
            for root_path in root_paths:
                dir_finished_callback(root_path, [])
        return []

    logger.info(f"扫描到 {total_files} 个 .m4s 文件，启动扁平并发分析 (max_workers={max_workers})")

    # 2. 初始化线程同步变量与结果容器
    lock = threading.Lock()
    completed_count = 0
    
    dir_results: Dict[str, List[StreamInfo]] = {dp: [] for dp in dir_to_files}
    dir_pending_count: Dict[str, int] = {dp: len(files) for dp, files in dir_to_files.items()}
    all_results: List[StreamInfo] = []

    # 3. 使用单层线程池进行并发流分析
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_file = {
            executor.submit(analyze_file, fp): fp for fp in flat_files
        }

        for future in as_completed(future_to_file):
            filepath = future_to_file[future]
            dirpath = os.path.dirname(filepath)
            
            try:
                info = future.result()
            except Exception as e:
                logger.error(f"分析文件失败: {filepath} - {e}")
                info = StreamInfo(
                    filepath=filepath,
                    stream_type=StreamType.UNKNOWN,
                    has_video=False,
                    has_audio=False,
                    error=str(e),
                )

            with lock:
                completed_count += 1
                all_results.append(info)
                
                # 更新对应目录的分析记录与计数
                if dirpath in dir_results:
                    dir_results[dirpath].append(info)
                    dir_pending_count[dirpath] -= 1
                    
                    # 当该目录下所有文件都已分析完毕时，触发增量回调
                    if dir_pending_count[dirpath] == 0:
                        logger.debug(f"目录下所有文件分析完毕: {dirpath}")
                        if dir_finished_callback:
                            try:
                                dir_finished_callback(dirpath, dir_results[dirpath])
                            except Exception as callback_err:
                                logger.error(f"执行 dir_finished_callback 回调异常: {callback_err}")

                if progress_callback:
                    try:
                        progress_callback(completed_count, total_files)
                    except Exception as progress_err:
                        logger.error(f"执行 progress_callback 进度回调异常: {progress_err}")

    logger.info(f"并发扫描分析完成: 共处理 {len(all_results)} 个文件")
    return all_results


def scan_directory(
    root_path: str,
    progress_callback: Optional[Callable[[int, int], None]] = None,
    max_workers: int = 4,
) -> List[StreamInfo]:
    """
    递归扫描目录，收集所有 .m4s 文件并分析流类型 (兼容单目录扫描接口)

    Args:
        root_path: 要扫描的根目录路径
        progress_callback: 进度回调函数，参数为 (已完成数, 总数)
        max_workers: 并发分析的最大线程数

    Returns:
        StreamInfo 对象列表
    """
    return scan_multiple_directories(
        [root_path],
        progress_callback=progress_callback,
        max_workers=max_workers
    )
