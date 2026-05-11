"""
文件扫描模块
负责递归扫描目录收集 .m4s 文件，并调用 ffprobe 分析流类型
"""

import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable, Optional

from fisheep_video_merger.utils.ffprobe import StreamInfo, StreamType, analyze_file
from fisheep_video_merger.utils.logger import get_logger

logger = get_logger()


def scan_directory(
    root_path: str,
    progress_callback: Optional[Callable[[int, int], None]] = None,
    max_workers: int = 4,
) -> list[StreamInfo]:
    """
    递归扫描目录，收集所有 .m4s 文件并分析流类型

    Args:
        root_path: 要扫描的根目录路径
        progress_callback: 进度回调函数，参数为 (已完成数, 总数)
        max_workers: 并发分析的最大线程数

    Returns:
        StreamInfo 对象列表
    """
    # 收集所有 .m4s 文件
    m4s_files: list[str] = []
    for dirpath, _, filenames in os.walk(root_path):
        for f in filenames:
            if f.lower().endswith(".m4s"):
                m4s_files.append(os.path.join(dirpath, f))

    if not m4s_files:
        logger.info(f"目录 '{root_path}' 中未找到 .m4s 文件")
        return []

    logger.info(f"在 '{root_path}' 中找到 {len(m4s_files)} 个 .m4s 文件，开始分析流类型")

    # 使用线程池并发分析
    results: list[StreamInfo] = []
    completed = 0
    total = len(m4s_files)

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_file = {
            executor.submit(analyze_file, f): f for f in m4s_files
        }

        for future in as_completed(future_to_file):
            filepath = future_to_file[future]
            try:
                info = future.result()
                results.append(info)
                logger.debug(
                    f"[{info.stream_type.value}] {os.path.basename(filepath)}"
                )
            except Exception as e:
                logger.error(f"分析文件失败: {filepath} - {e}")
                results.append(
                    StreamInfo(
                        filepath=filepath,
                        stream_type=StreamType.UNKNOWN,
                        has_video=False,
                        has_audio=False,
                        error=str(e),
                    )
                )

            completed += 1
            if progress_callback:
                progress_callback(completed, total)

    logger.info(f"扫描完成: 共 {len(results)} 个文件")
    return results


def scan_multiple_directories(
    root_paths: list[str],
    progress_callback: Optional[Callable[[int, int], None]] = None,
    max_workers: int = 4,
) -> list[StreamInfo]:
    """
    扫描多个目录

    Args:
        root_paths: 根目录路径列表
        progress_callback: 进度回调
        max_workers: 最大线程数

    Returns:
        合并后的 StreamInfo 列表
    """
    all_results: list[StreamInfo] = []
    total_dirs = len(root_paths)

    for i, root_path in enumerate(root_paths):
        logger.info(f"扫描目录 ({i + 1}/{total_dirs}): {root_path}")
        results = scan_directory(
            root_path,
            progress_callback=progress_callback,
            max_workers=max_workers,
        )
        all_results.extend(results)

    return all_results
