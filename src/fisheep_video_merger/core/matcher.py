"""
配对模块
负责自动配对和手动配对逻辑
"""

import os
import re
from dataclasses import dataclass, field
from typing import Optional, List, Tuple, Callable

from fisheep_video_merger.utils.ffprobe import StreamInfo, StreamType
from fisheep_video_merger.utils.logger import get_logger

logger = get_logger()

# 中文数字映射
_CN_NUM_MAP = {
    "零": 0, "一": 1, "二": 2, "两": 2, "三": 3, "四": 4,
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


# 声明式集数匹配与清理配置
# 元组格式: (匹配模式正则, 提取处理器函数, 清理模式正则, 正则标志)
EPISODE_PATTERNS: List[Tuple[str, Callable[[re.Match], Optional[int]], str, int]] = [
    # 模式1: 第\d+集 / 第X集（支持 集/话/篇/幕/次/期/回/P）
    (
        r"第\s*(\d+)\s*[集话篇幕次期回P]",
        lambda m: int(m.group(1)),
        r"第\s*\d+\s*[集话篇幕次期回P]",
        re.IGNORECASE
    ),
    (
        r"第\s*([零一二两三四五六七八九十百千]+)\s*[集话篇幕次期回]",
        lambda m: _parse_chinese_number(m.group(1)),
        r"第\s*[零一二两三四五六七八九十百千]+\s*[集话篇幕次期回]",
        0
    ),
    # 模式2: EP\d+ / Part\d+ / P\d+
    (
        r"(?:EP|Ep|ep|Part|part|P|p)\s*(\d+)",
        lambda m: int(m.group(1)),
        r"(?:EP|Ep|ep|Part|part|P|p)\s*\d+",
        re.IGNORECASE
    ),
    # 模式3: E\d+（单独的 E 后跟数字，但不是单词的一部分）
    (
        r"(?<![a-zA-Z])E\s*(\d+)",
        lambda m: int(m.group(1)),
        r"(?<![a-zA-Z])E\s*\d+",
        re.IGNORECASE
    ),
    # 模式4: #\d+
    (
        r"#\s*(\d+)",
        lambda m: int(m.group(1)),
        r"#\s*\d+",
        0
    ),
    # 模式5: 各种括弧包裹的数字，如 (03)、[3]、【03】
    (
        r"[\(\[【]\s*(\d+)\s*[\)\]】]",
        lambda m: int(m.group(1)),
        r"[\(\[【]\s*\d+\s*[\)\]】]",
        0
    ),
    # 模式6: 前缀数字模式，常用于 "01. 这是一个视频.m4s"
    # 限制1-4位数，避免匹配到分辨率等大数字（如 "1080 xxx"）
    (
        r"^(\d{1,4})[\s._-]+",
        lambda m: int(m.group(1)),
        r"^[\s._-]*\d+[\s._-]+",
        0
    ),
    # 模式7: 文件名末尾或倒数第二部分为纯数字（至少2位，避免误判）
    (
        r"[-_\s]+(\d{2,})$",
        lambda m: int(m.group(1)),
        r"[-_\s]+\d{2,}$",
        0
    ),
]


def extract_episode_number(filename: str) -> Optional[int]:
    """
    从文件名中提取集数

    支持以下模式（不区分大小写）：
    - `第3集`, `第03话`, `第3幕` (支持多种中文量词)
    - `第两百集`, `第十二话` (支持繁体/口语化中文数字)
    - `EP03`, `EP3`, `Ep03`
    - `Part 1`, `part 01`, `P1`, `p02` (分P标识)
    - `E03`, `e3`
    - `#03`, `#3`
    - `(03)`, `[3]`, `【03】` (括弧封装数字)
    - `01.xxx` (前缀序号模式)
    - `03` (纯数字作为文件名末尾或倒数第二部分)

    Args:
        filename: 文件名（不含路径）

    Returns:
        集数（从 1 开始），如果未找到则返回 None
    """
    name, _ = os.path.splitext(filename)
    for pattern, processor, _, flags in EPISODE_PATTERNS:
        m = re.search(pattern, name, flags)
        if m:
            val = processor(m)
            if val is not None:
                return val
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
        # 顺序执行清理，从原始名称中移除集数信息后作为前缀
        clean = name_without_ext
        for _, _, clean_pat, flags in EPISODE_PATTERNS:
            clean = re.sub(clean_pat, "", clean, flags=flags)
        clean = clean.strip("-_ .")

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


def _find_root_for_file(filepath: str, root_paths: list[str]) -> str:
    """找到文件所属的根路径，若找不到则返回空字符串或第一个根路径"""
    for root in root_paths:
        try:
            common = os.path.commonpath([root, filepath])
            if common == root:
                return root
        except ValueError:
            continue
    return root_paths[0] if root_paths else ""


# ====================================================================
# 🧩 匹配引擎策略模式重构 (Strategy Pattern for Matching Engine)
# ====================================================================

class MatchStrategy:
    """配对策略基类"""
    def match(
        self,
        videos: List[StreamInfo],
        audios: List[StreamInfo],
        root_paths: List[str],
        result: MatchResult,
    ) -> Tuple[List[StreamInfo], List[StreamInfo]]:
        """
        执行配对
        Args:
            videos: 候选视频流列表
            audios: 候选音频流列表
            root_paths: 拖入的根目录列表
            result: 配对结果容器（将匹配的任务直接添加到 result.auto_tasks 中）
        Returns:
            未被当前策略匹配的 (剩余视频流列表, 剩余音频流列表)
        """
        raise NotImplementedError


class DirectoryMatchStrategy(MatchStrategy):
    """
    目录级配对策略
    对同一最底层子文件夹内的音视频进行配对：
    - 1v1: 自动配对
    - NvN (N > 1): 按文件名排序后配对，标记多集
    """
    def match(
        self,
        videos: List[StreamInfo],
        audios: List[StreamInfo],
        root_paths: List[str],
        result: MatchResult,
    ) -> Tuple[List[StreamInfo], List[StreamInfo]]:
        # 按文件所在目录对文件进行分组
        def get_dir(info: StreamInfo) -> str:
            return os.path.dirname(info.filepath)

        dir_videos: dict[str, List[StreamInfo]] = {}
        for v in videos:
            dir_videos.setdefault(get_dir(v), []).append(v)

        dir_audios: dict[str, List[StreamInfo]] = {}
        for a in audios:
            dir_audios.setdefault(get_dir(a), []).append(a)

        all_dirs = set(dir_videos.keys()) | set(dir_audios.keys())
        
        remaining_videos: List[StreamInfo] = []
        remaining_audios: List[StreamInfo] = []

        for dirpath in all_dirs:
            v_list = dir_videos.get(dirpath, [])
            a_list = dir_audios.get(dirpath, [])
            
            root_path = _find_root_for_file(dirpath, root_paths)

            if len(v_list) == 1 and len(a_list) == 1:
                # 单对单：智能提取集数信息作为输出名
                v = v_list[0]
                a = a_list[0]
                output_name = normalize_episode_name(v.filepath)
                task = MergeTask(
                    output_name=output_name,
                    video_file=v.filepath,
                    audio_file=a.filepath,
                    source_dir=dirpath,
                    root_path=root_path,
                )
                result.auto_tasks.append(task)
                logger.info(f"自动配对 (1v1): {output_name} ({v.filepath} + {a.filepath})")

            elif len(v_list) == len(a_list) and len(v_list) > 1:
                # 多对多等量：按文件名排序后配对
                v_list.sort(key=lambda x: os.path.basename(x.filepath))
                a_list.sort(key=lambda x: os.path.basename(x.filepath))

                folder_name = os.path.basename(dirpath)

                for i, (v, a) in enumerate(zip(v_list, a_list)):
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
                        root_path=root_path,
                        is_multi_episode=True,
                    )
                    result.auto_tasks.append(task)
                    logger.info(f"自动配对(多集): {task.output_name}")
            else:
                # 数量不对等，暂不配对，保留到下一阶段的全局智能求解器
                remaining_videos.extend(v_list)
                remaining_audios.extend(a_list)

        return remaining_videos, remaining_audios


class CleanStemMatchStrategy(MatchStrategy):
    """
    纯净骨架名称配对策略 (Clean Stem Matcher)
    移除如 ".video", ".audio", "30280"(流ID), "_v", "_a" 等常见尾赘后，若文件名骨干一致则强绑定
    仅在音频也是唯一对应的情况下绑定，防止引发大规模的多对多歧义
    """
    def match(
        self,
        videos: List[StreamInfo],
        audios: List[StreamInfo],
        root_paths: List[str],
        result: MatchResult,
    ) -> Tuple[List[StreamInfo], List[StreamInfo]]:
        if not videos or not audios:
            return videos, audios

        def get_clean_stem(filename: str) -> str:
            stem, _ = os.path.splitext(filename)
            # 1. 移除音视频流方向后缀
            stem = re.sub(r"[-_.](?:video|audio|v|a)$", "", stem, flags=re.IGNORECASE)
            # 2. 移除常见 B站/FFmpeg 合并可能产生的数字 ID（如码率ID 30280 / 30216 等）
            stem = re.sub(r"[-_](?:30280|30216|30232|30080|30120|120|80|64)$", "", stem)
            return stem.strip().lower()

        # 建立音频骨架哈希库
        audio_stems: dict[str, List[StreamInfo]] = {}
        for a in audios:
            astem = get_clean_stem(os.path.basename(a.filepath))
            audio_stems.setdefault(astem, []).append(a)

        matched_video_paths = set()
        matched_audio_paths = set()

        for v in videos:
            vstem = get_clean_stem(os.path.basename(v.filepath))
            if vstem in audio_stems:
                candidates = audio_stems[vstem]
                # 仅在音频也是唯一对应的情况下绑定，防止歧义
                if len(candidates) == 1:
                    a = candidates[0]
                    if a.filepath not in matched_audio_paths:
                        out_name = normalize_episode_name(v.filepath)
                        task = MergeTask(
                            output_name=out_name,
                            video_file=v.filepath,
                            audio_file=a.filepath,
                            source_dir=os.path.dirname(v.filepath),
                            root_path=_find_root_for_file(v.filepath, root_paths),
                        )
                        result.auto_tasks.append(task)
                        matched_video_paths.add(v.filepath)
                        matched_audio_paths.add(a.filepath)
                        logger.info(f"🔍 [骨架智能配对] 绑定: {out_name}")

        remaining_videos = [x for x in videos if x.filepath not in matched_video_paths]
        remaining_audios = [x for x in audios if x.filepath not in matched_audio_paths]
        return remaining_videos, remaining_audios


class EpisodeInterlockStrategy(MatchStrategy):
    """
    集数互锁解题器策略 (Episode Interlocking Solver)
    针对散落的流，如果某个集数全局只剩唯一的一个视频和一个音频，即可认定互锁并进行配对
    """
    def match(
        self,
        videos: List[StreamInfo],
        audios: List[StreamInfo],
        root_paths: List[str],
        result: MatchResult,
    ) -> Tuple[List[StreamInfo], List[StreamInfo]]:
        if not videos or not audios:
            return videos, audios

        # 提取并按集数分组视频
        v_by_ep: dict[int, List[StreamInfo]] = {}
        for v in videos:
            ep = extract_episode_number(os.path.basename(v.filepath))
            if ep is not None:
                v_by_ep.setdefault(ep, []).append(v)

        # 提取并按集数分组音频
        a_by_ep: dict[int, List[StreamInfo]] = {}
        for a in audios:
            ep = extract_episode_number(os.path.basename(a.filepath))
            if ep is not None:
                a_by_ep.setdefault(ep, []).append(a)

        matched_video_paths = set()
        matched_audio_paths = set()

        # 对相同集数寻求闭锁点
        for ep, vs in v_by_ep.items():
            if ep in a_by_ep:
                as_ = a_by_ep[ep]
                # 唯一互锁判定
                if len(vs) == 1 and len(as_) == 1:
                    v = vs[0]
                    a = as_[0]
                    if a.filepath not in matched_audio_paths:
                        out_name = normalize_episode_name(v.filepath)
                        task = MergeTask(
                            output_name=out_name,
                            video_file=v.filepath,
                            audio_file=a.filepath,
                            source_dir=os.path.dirname(v.filepath),
                            root_path=_find_root_for_file(v.filepath, root_paths),
                        )
                        result.auto_tasks.append(task)
                        matched_video_paths.add(v.filepath)
                        matched_audio_paths.add(a.filepath)
                        logger.info(f"🎯 [集数互锁配对] 绑定: {out_name} (第 {ep} 集)")

        remaining_videos = [x for x in videos if x.filepath not in matched_video_paths]
        remaining_audios = [x for x in audios if x.filepath not in matched_audio_paths]
        return remaining_videos, remaining_audios


class MatcherPipeline:
    """
    匹配执行管道
    允许注册多个配对策略并按顺序执行，支持极高的扩展性。
    """
    def __init__(self, strategies: List[MatchStrategy] = None):
        self.strategies = strategies or [
            DirectoryMatchStrategy(),
            CleanStemMatchStrategy(),
            EpisodeInterlockStrategy(),
        ]

    def execute(
        self,
        stream_infos: List[StreamInfo],
        root_paths: List[str],
    ) -> MatchResult:
        result = MatchResult()

        # 分类初始流类型
        videos = [f for f in stream_infos if f.stream_type == StreamType.VIDEO_ONLY]
        audios = [f for f in stream_infos if f.stream_type == StreamType.AUDIO_ONLY]
        muxed = [f for f in stream_infos if f.stream_type == StreamType.MUXED]

        result.muxed_files.extend(muxed)

        # 顺序调用配对策略链进行过滤
        curr_videos, curr_audios = videos, audios
        for strategy in self.strategies:
            curr_videos, curr_audios = strategy.match(
                curr_videos,
                curr_audios,
                root_paths,
                result,
            )

        # 无法被任何策略配对成功的流，归入待整理队列
        result.pending_videos.extend(curr_videos)
        result.pending_audios.extend(curr_audios)

        total_saved = len(videos) - len(curr_videos)
        if total_saved > 0:
            logger.info(f"🎯 智能配对管线成功挽救并配对 {total_saved} 对散流文件")

        return result


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

    通过管道式策略模式链式运行（包括骨架分析和集数互锁）

    Args:
        stream_infos: 所有文件的流信息列表
        root_paths: 用户拖入的根目录列表

    Returns:
        MatchResult 包含自动配对任务和剩余文件
    """
    pipeline = MatcherPipeline()
    return pipeline.execute(stream_infos, root_paths)


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
