"""
配对模块
负责自动配对和手动配对逻辑
"""

import os
import re
from dataclasses import dataclass, field
from typing import Optional

from fisheep_video_merger.utils.ffprobe import StreamInfo, StreamType
from fisheep_video_merger.utils.logger import get_logger

logger = get_logger()

# 中文数字映射
_CN_NUM_MAP = {
    "零": 0, "一": 1, "二": 2, "三": 3, "四": 4,
    "五": 5, "六": 6, "七": 7, "八": 8, "九": 9,
    "十": 10, "百": 100, "千": 1000,
}


def _parse_chinese_number(text: str) -> Optional[int]:
    """
    将中文数字字符串转换为阿拉伯数字

    Args:
        text: 中文数字，如 "三"、"十二"、"二十五"、"一百"

    Returns:
        阿拉伯数字，或 None 如果无法解析
    """
    if not text:
        return None

    # 先尝试直接映射（个位数）
    if text in _CN_NUM_MAP:
        val = _CN_NUM_MAP[text]
        if val < 10:
            return val

    # 处理"十X"、"X十"、"X十X"等组合
    total = 0
    current = 0
    for char in text:
        if char in _CN_NUM_MAP:
            num = _CN_NUM_MAP[char]
            if num >= 10:
                # 遇到"十"、"百"、"千"：乘以当前值，若当前为0则设为1
                if current == 0:
                    current = 1
                total += current * num
                current = 0
            else:
                current = num
        else:
            return None
    total += current

    return total if total > 0 else None


def extract_episode_number(filename: str) -> Optional[int]:
    """
    从文件名中提取集数

    支持以下模式（不区分大小写）：
    - `第3集`, `第03集` (中文"第X集")
    - `第三集` (中文数字)
    - `EP03`, `EP3`, `Ep03`
    - `E03`, `e3`
    - `#03`, `#3`
    - `(03)`, `(3)`
    - `03` (纯数字作为文件名末尾或倒数第二部分)

    Args:
        filename: 文件名（不含路径）

    Returns:
        集数（从 1 开始），如果未找到则返回 None
    """
    name, _ = os.path.splitext(filename)

    # 模式1: 第\d+集 / 第X集（中文数字）
    m = re.search(r"第\s*(\d+)\s*集", name)
    if m:
        return int(m.group(1))

    m = re.search(r"第\s*([零一二三四五六七八九十百千]+)\s*集", name)
    if m:
        return _parse_chinese_number(m.group(1))

    # 模式2: EP\d+ / Ep\d+ / ep\d+
    m = re.search(r"(?:EP|Ep|ep)\s*(\d+)", name)
    if m:
        return int(m.group(1))

    # 模式3: E\d+（单独的 E 后跟数字，但不是单词的一部分）
    m = re.search(r"(?<![a-zA-Z])E\s*(\d+)", name)
    if m:
        return int(m.group(1))

    # 模式4: #\d+
    m = re.search(r"#\s*(\d+)", name)
    if m:
        return int(m.group(1))

    # 模式5: (数字) 如 name(03).m4s 或 name (03).m4s
    m = re.search(r"\((\d+)\)", name)
    if m:
        return int(m.group(1))

    # 模式6: 文件名末尾或倒数第二部分为纯数字（至少2位，避免误判）
    # 匹配如 "name_03"、"name-03"、"name 03" 等
    m = re.search(r"[-_\s]+(\d{2,})$", name)
    if m:
        return int(m.group(1))

    return None


def normalize_episode_name(video_filename: str) -> str:
    """
    根据视频文件名智能生成输出文件名

    如果文件名中包含集数信息（如"第3集"、"EP03"等），
    则提取集数并格式化为 _NN（2位）作为输出文件名。

    Args:
        video_filename: 视频文件完整路径

    Returns:
        输出文件名（不含扩展名）
    """
    basename = os.path.basename(video_filename)
    name_without_ext, _ = os.path.splitext(basename)

    ep = extract_episode_number(basename)
    if ep is not None:
        # 从原始名称中移除集数信息后作为前缀
        # 移除已知的集数模式，保留有意义的前缀
        clean = re.sub(
            r"第\s*\d+\s*集|第\s*[零一二三四五六七八九十百千]+\s*集"
            r"|(?:EP|Ep|ep)\s*\d+|(?<![a-zA-Z])E\s*\d+"
            r"|#\s*\d+|\(\d+\)|[-_\s]+\d{2,}$",
            "",
            name_without_ext,
        ).strip("-_ .")

        # 如果清理后非空，用清理后的前缀 + 集数
        if clean:
            # 移除连续的多个分隔符
            clean = re.sub(r"[-_\s]+", "_", clean).strip("_")
            return f"{clean}_{ep:02d}"
        else:
            # 如果清理后为空（文件名就是"第3集"这样的纯集数），直接用集数
            return f"E{ep:02d}"

    # 未检测到集数信息，返回原始文件名
    return name_without_ext


@dataclass
class MergeTask:
    """单个合并任务"""
    output_name: str
    video_file: str
    audio_file: str
    source_dir: str  # 源文件所在目录
    root_path: str   # 所属的拖入根目录
    status: str = "pending"  # pending / success / error
    error_message: Optional[str] = None
    is_multi_episode: bool = False  # 是否标记为多集


@dataclass
class MatchResult:
    """配对结果"""
    auto_tasks: list[MergeTask] = field(default_factory=list)
    pending_videos: list[StreamInfo] = field(default_factory=list)
    pending_audios: list[StreamInfo] = field(default_factory=list)
    muxed_files: list[StreamInfo] = field(default_factory=list)


def _get_relative_dir(filepath: str, root_path: str) -> str:
    """获取文件相对于根目录的目录路径"""
    file_dir = os.path.dirname(filepath)
    try:
        rel = os.path.relpath(file_dir, root_path)
        if rel == ".":
            return ""
        return rel
    except ValueError:
        return ""


def auto_match(
    stream_infos: list[StreamInfo],
    root_paths: list[str],
) -> MatchResult:
    """
    自动配对逻辑

    对每个最底层子文件夹进行分析：
    - 1 video + 1 audio → 自动配对
    - N video + N audio (N>1) → 按字典序配对，标记多集
    - 数量不对等 → 留入待整理
    - muxed → 单独列表

    Args:
        stream_infos: 所有文件的流信息列表
        root_paths: 用户拖入的根目录列表

    Returns:
        MatchResult 包含自动配对任务和剩余文件
    """
    result = MatchResult()

    # 按文件所在目录分组
    dir_groups: dict[str, list[StreamInfo]] = {}
    for info in stream_infos:
        file_dir = os.path.dirname(info.filepath)
        if file_dir not in dir_groups:
            dir_groups[file_dir] = []
        dir_groups[file_dir].append(info)

    # 找到每个文件所属的根路径
    def find_root(filepath: str) -> Optional[str]:
        for root in root_paths:
            try:
                common = os.path.commonpath([root, filepath])
                if common == root:
                    return root
            except ValueError:
                continue
        return None

    # 处理每个目录
    for dirpath, files in dir_groups.items():
        videos = [f for f in files if f.stream_type == StreamType.VIDEO_ONLY]
        audios = [f for f in files if f.stream_type == StreamType.AUDIO_ONLY]
        muxed = [f for f in files if f.stream_type == StreamType.MUXED]

        # 收集 muxed 文件
        result.muxed_files.extend(muxed)

        # 确定根路径
        root_path = find_root(dirpath)
        if root_path is None and root_paths:
            root_path = root_paths[0]

        # 自动配对逻辑
        if len(videos) == 1 and len(audios) == 1:
            # 单对：智能提取集数信息作为输出名
            output_name = normalize_episode_name(videos[0].filepath)
            task = MergeTask(
                output_name=output_name,
                video_file=videos[0].filepath,
                audio_file=audios[0].filepath,
                source_dir=dirpath,
                root_path=root_path or "",
            )
            result.auto_tasks.append(task)
            logger.info(f"自动配对: {output_name} ({videos[0].filepath} + {audios[0].filepath})")

        elif len(videos) == len(audios) and len(videos) > 1:
            # 多对，按文件名排序后配对
            videos.sort(key=lambda x: os.path.basename(x.filepath))
            audios.sort(key=lambda x: os.path.basename(x.filepath))

            # 尝试从第一个视频文件名提取集数，作为基准
            first_ep = extract_episode_number(os.path.basename(videos[0].filepath))
            folder_name = os.path.basename(dirpath)

            for i, (v, a) in enumerate(zip(videos, audios)):
                # 尝试从当前视频文件名提取集数
                current_ep = extract_episode_number(os.path.basename(v.filepath))
                if current_ep is not None:
                    output_name = f"{current_ep:02d}"
                    # 如果目录名有含义，加上前缀
                    clean_folder = re.sub(r"[-_\s]+", "_", folder_name).strip("_")
                    if clean_folder and not re.match(r"^[\d]+$", clean_folder):
                        output_name = f"{clean_folder}_{current_ep:02d}"
                else:
                    output_name = f"{folder_name}_{i + 1:02d}"

                task = MergeTask(
                    output_name=output_name,
                    video_file=v.filepath,
                    audio_file=a.filepath,
                    source_dir=dirpath,
                    root_path=root_path or "",
                    is_multi_episode=True,
                )
                result.auto_tasks.append(task)
                logger.info(f"自动配对(多集): {task.output_name}")

        else:
            # 数量不对等，留入待整理
            result.pending_videos.extend(videos)
            result.pending_audios.extend(audios)
            if videos or audios:
                logger.info(
                    f"目录 '{dirpath}' 数量不对等 "
                    f"(视频:{len(videos)}, 音频:{len(audios)})，留入待整理"
                )

    return result


def create_manual_task(
    video_info: StreamInfo,
    audio_info: StreamInfo,
    output_name: str,
    root_path: str,
) -> MergeTask:
    """
    创建手动配对任务

    Args:
        video_info: 视频文件信息
        audio_info: 音频文件信息
        output_name: 输出文件名（不含扩展名）
        root_path: 所属根路径

    Returns:
        合并任务
    """
    file_dir = os.path.dirname(video_info.filepath)
    task = MergeTask(
        output_name=output_name,
        video_file=video_info.filepath,
        audio_file=audio_info.filepath,
        source_dir=file_dir,
        root_path=root_path,
    )
    logger.info(f"手动配对: {output_name}")
    return task
