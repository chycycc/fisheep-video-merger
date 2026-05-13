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

    # 模式1: 第\d+集 / 第X集（支持 集/话/篇/幕/次/期/P）
    m = re.search(r"第\s*(\d+)\s*[集话篇幕次期P]", name, re.IGNORECASE)
    if m:
        return int(m.group(1))

    m = re.search(r"第\s*([零一二两三四五六七八九十百千]+)\s*[集话篇幕次期]", name)
    if m:
        return _parse_chinese_number(m.group(1))

    # 模式2: EP\d+ / Part\d+ / P\d+
    m = re.search(r"(?:EP|Ep|ep|Part|part|P|p)\s*(\d+)", name)
    if m:
        return int(m.group(1))

    # 模式3: E\d+（单独的 E 后跟数字，但不是单词的一部分）
    m = re.search(r"(?<![a-zA-Z])E\s*(\d+)", name, re.IGNORECASE)
    if m:
        return int(m.group(1))

    # 模式4: #\d+
    m = re.search(r"#\s*(\d+)", name)
    if m:
        return int(m.group(1))

    # 模式5: 各种括弧包裹的数字，如 (03)、[3]、【03】
    m = re.search(r"[\(\[【]\s*(\d+)\s*[\)\]】]", name)
    if m:
        return int(m.group(1))

    # 模式6: 前缀数字模式，常用于 "01. 这是一个视频.m4s"
    m = re.search(r"^(\d+)[\s._-]+", name)
    if m:
        return int(m.group(1))

    # 模式7: 文件名末尾或倒数第二部分为纯数字（至少2位，避免误判）
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
            r"第\s*\d+\s*[集话篇幕次期P]|第\s*[零一二两三四五六七八九十百千]+\s*[集话篇幕次期]"
            r"|(?:EP|Ep|ep|Part|part|P|p)\s*\d+|(?<![a-zA-Z])E\s*\d+"
            r"|#\s*\d+|[\(\[【]\s*\d+\s*[\)\]】]|^[\s._-]*\d+[\s._-]+"
            r"|[-_\s]+\d{2,}$",
            "",
            name_without_ext,
            flags=re.IGNORECASE,
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
            # 数量不对等，先全部送入待整理，稍后通过全局智能解题器进一步过滤配对
            result.pending_videos.extend(videos)
            result.pending_audios.extend(audios)

    # ==========================================
    # 💡 核心智能算法升级：待整理区异步精准求解器 (Smart Solver)
    # ==========================================
    # 当一个文件夹由于丢帧或下载中断等造成音视频数量不对等时，上面的严格配对逻辑会放弃整组。
    # 这里的求解器会跳过“必须等长”约束，在全部零散流文件中寻找最佳前缀匹配和集数互锁配对。
    
    if result.pending_videos and result.pending_audios:
        matched_video_paths = set()
        matched_audio_paths = set()

        # --- 辅助：获取文件所属的根目录 ---
        def _find_root_for_file(fp: str) -> str:
            root = find_root(fp)
            if root:
                return root
            return root_paths[0] if root_paths else ""

        # --- 策略 A: 纯净骨架名称配对 (Clean Stem Matcher) ---
        # 移除如 ".video", ".audio", "30280"(流ID), "_v", "_a" 等常见尾赘后，若文件名骨干一致则强绑定
        def get_clean_stem(filename: str) -> str:
            stem, _ = os.path.splitext(filename)
            # 1. 移除音视频流方向后缀
            stem = re.sub(r"[-_.](?:video|audio|v|a)$", "", stem, flags=re.IGNORECASE)
            # 2. 移除常见 B站/FFmpeg 合并可能产生的数字 ID（如码率ID 30280 / 30216，或分片标志）
            stem = re.sub(r"[-_](?:30280|30216|30232|30080|30120|120|80|64)$", "", stem)
            return stem.strip().lower()

        # 建立音频骨架哈希库
        audio_stems: dict[str, list[StreamInfo]] = {}
        for a in result.pending_audios:
            astem = get_clean_stem(os.path.basename(a.filepath))
            if astem not in audio_stems:
                audio_stems[astem] = []
            audio_stems[astem].append(a)

        # 扫描视频尝试通过骨架名称锁定唯一匹配的音频
        for v in result.pending_videos:
            vstem = get_clean_stem(os.path.basename(v.filepath))
            if vstem in audio_stems:
                candidates = audio_stems[vstem]
                # 仅在音频也是唯一对应的情况下绑定，防止引发大规模的多对多歧义
                if len(candidates) == 1:
                    a = candidates[0]
                    if a.filepath not in matched_audio_paths:
                        out_name = normalize_episode_name(v.filepath)
                        task = MergeTask(
                            output_name=out_name,
                            video_file=v.filepath,
                            audio_file=a.filepath,
                            source_dir=os.path.dirname(v.filepath),
                            root_path=_find_root_for_file(v.filepath),
                        )
                        result.auto_tasks.append(task)
                        matched_video_paths.add(v.filepath)
                        matched_audio_paths.add(a.filepath)
                        logger.info(f"🔍 [骨架智能配对] 绑定: {out_name}")

        # --- 策略 B: 集数互锁解题器 (Episode Interlocking Solver) ---
        # 针对上面未配对成功的极其散落的流，如果在剩余集合中，某个集数全局只剩唯一的一个视频和一个音频，即可认定互锁
        rem_videos = [x for x in result.pending_videos if x.filepath not in matched_video_paths]
        rem_audios = [x for x in result.pending_audios if x.filepath not in matched_audio_paths]

        if rem_videos and rem_audios:
            v_by_ep: dict[int, list[StreamInfo]] = {}
            for v in rem_videos:
                ep = extract_episode_number(os.path.basename(v.filepath))
                if ep is not None:
                    if ep not in v_by_ep:
                        v_by_ep[ep] = []
                    v_by_ep[ep].append(v)

            a_by_ep: dict[int, list[StreamInfo]] = {}
            for a in rem_audios:
                ep = extract_episode_number(os.path.basename(a.filepath))
                if ep is not None:
                    if ep not in a_by_ep:
                        a_by_ep[ep] = []
                    a_by_ep[ep].append(a)

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
                                root_path=_find_root_for_file(v.filepath),
                            )
                            result.auto_tasks.append(task)
                            matched_video_paths.add(v.filepath)
                            matched_audio_paths.add(a.filepath)
                            logger.info(f"🎯 [集数互锁配对] 绑定: {out_name} (第 {ep} 集)")

        # 从待整理列表中剔除已被成功解题匹配的项目
        if matched_video_paths or matched_audio_paths:
            result.pending_videos = [x for x in result.pending_videos if x.filepath not in matched_video_paths]
            result.pending_audios = [x for x in result.pending_audios if x.filepath not in matched_audio_paths]
            logger.info(f"🎯 智能解题器成功挽救并配对 {len(matched_video_paths)} 对散流文件")

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
