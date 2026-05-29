"""
配对模块
负责自动配对和手动配对逻辑（策略模式匹配管道）
"""

import os
import re
from typing import List, Tuple

from fisheep_video_merger.core.models import MergeTask, MatchResult
from fisheep_video_merger.core.episode import extract_episode_number, normalize_episode_name
from fisheep_video_merger.core.naming import suggest_output_name
from fisheep_video_merger.utils.ffprobe import StreamInfo, StreamType
from fisheep_video_merger.utils.logger import get_logger

logger = get_logger()

# 公开 API（向后兼容）
from fisheep_video_merger.core.bilibili import read_bilibili_meta
from fisheep_video_merger.core.naming import apply_naming_template


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
# 🧩 匹配引擎策略模式 (Strategy Pattern)
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
                v = v_list[0]
                a = a_list[0]
                output_name = suggest_output_name(v.filepath, dirpath, root_path)
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
                folder_name = os.path.basename(dirpath)

                a_by_ep: dict[int, StreamInfo] = {}
                a_no_ep: list[StreamInfo] = []
                for a in a_list:
                    ep = extract_episode_number(os.path.basename(a.filepath))
                    if ep is not None and ep not in a_by_ep:
                        a_by_ep[ep] = a
                    else:
                        a_no_ep.append(a)

                matched_audio_paths: set[str] = set()

                for v in v_list:
                    v_ep = extract_episode_number(os.path.basename(v.filepath))
                    matched_audio = None

                    if v_ep is not None and v_ep in a_by_ep:
                        matched_audio = a_by_ep[v_ep]
                        matched_audio_paths.add(matched_audio.filepath)

                    if matched_audio is None:
                        for a in a_list:
                            if a.filepath not in matched_audio_paths:
                                matched_audio = a
                                matched_audio_paths.add(a.filepath)
                                logger.warning(f"NvN 降级配对（无集数匹配）: {v.filepath} + {a.filepath}")
                                break

                    if matched_audio is None:
                        logger.error(f"未找到匹配音频: {v.filepath}")
                        continue

                    if v_ep is not None:
                        clean_folder = re.sub(r"[-_\s]+", "_", folder_name).strip("_")
                        if clean_folder and not re.match(r"^[\d]+$", clean_folder):
                            output_name = f"{clean_folder}_{v_ep:02d}"
                        else:
                            output_name = f"{v_ep:02d}"
                    else:
                        output_name = normalize_episode_name(v.filepath)

                    task = MergeTask(
                        output_name=output_name,
                        video_file=v.filepath,
                        audio_file=matched_audio.filepath,
                        source_dir=dirpath,
                        root_path=root_path,
                        is_multi_episode=True,
                    )
                    result.auto_tasks.append(task)
                    logger.info(f"自动配对(多集): {task.output_name}")
            else:
                remaining_videos.extend(v_list)
                remaining_audios.extend(a_list)

        return remaining_videos, remaining_audios


class CleanStemMatchStrategy(MatchStrategy):
    """
    纯净骨架名称配对策略
    移除如 ".video", ".audio", "30280"(流ID) 等常见尾赘后，若文件名骨干一致则强绑定
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
            stem = re.sub(r"[-_.](?:video|audio|v|a)$", "", stem, flags=re.IGNORECASE)
            stem = re.sub(r"[-_](?:30280|30216|30232|30080|30120|120|80|64)$", "", stem)
            return stem.strip().lower()

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
                if len(candidates) == 1:
                    a = candidates[0]
                    if a.filepath not in matched_audio_paths:
                        src_dir = os.path.dirname(v.filepath)
                        rp = _find_root_for_file(v.filepath, root_paths)
                        out_name = suggest_output_name(v.filepath, src_dir, rp)
                        task = MergeTask(
                            output_name=out_name,
                            video_file=v.filepath,
                            audio_file=a.filepath,
                            source_dir=src_dir,
                            root_path=rp,
                        )
                        result.auto_tasks.append(task)
                        matched_video_paths.add(v.filepath)
                        matched_audio_paths.add(a.filepath)
                        logger.info(f"骨架智能配对: {out_name}")

        remaining_videos = [x for x in videos if x.filepath not in matched_video_paths]
        remaining_audios = [x for x in audios if x.filepath not in matched_audio_paths]
        return remaining_videos, remaining_audios


class EpisodeInterlockStrategy(MatchStrategy):
    """
    集数互锁解题器策略
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

        v_by_ep: dict[int, List[StreamInfo]] = {}
        for v in videos:
            ep = extract_episode_number(os.path.basename(v.filepath))
            if ep is not None:
                v_by_ep.setdefault(ep, []).append(v)

        a_by_ep: dict[int, List[StreamInfo]] = {}
        for a in audios:
            ep = extract_episode_number(os.path.basename(a.filepath))
            if ep is not None:
                a_by_ep.setdefault(ep, []).append(a)

        matched_video_paths = set()
        matched_audio_paths = set()

        for ep, vs in v_by_ep.items():
            if ep in a_by_ep:
                as_ = a_by_ep[ep]
                if len(vs) == 1 and len(as_) == 1:
                    v = vs[0]
                    a = as_[0]
                    if a.filepath not in matched_audio_paths:
                        src_dir = os.path.dirname(v.filepath)
                        rp = _find_root_for_file(v.filepath, root_paths)
                        out_name = suggest_output_name(v.filepath, src_dir, rp)
                        task = MergeTask(
                            output_name=out_name,
                            video_file=v.filepath,
                            audio_file=a.filepath,
                            source_dir=src_dir,
                            root_path=rp,
                        )
                        result.auto_tasks.append(task)
                        matched_video_paths.add(v.filepath)
                        matched_audio_paths.add(a.filepath)
                        logger.info(f"集数互锁配对: {out_name} (第 {ep} 集)")

        remaining_videos = [x for x in videos if x.filepath not in matched_video_paths]
        remaining_audios = [x for x in audios if x.filepath not in matched_audio_paths]
        return remaining_videos, remaining_audios


class MatcherPipeline:
    """
    匹配执行管道
    允许注册多个配对策略并按顺序执行
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

        videos = [f for f in stream_infos if f.stream_type == StreamType.VIDEO_ONLY]
        audios = [f for f in stream_infos if f.stream_type == StreamType.AUDIO_ONLY]
        muxed = [f for f in stream_infos if f.stream_type == StreamType.MUXED]

        result.muxed_files.extend(muxed)

        curr_videos, curr_audios = videos, audios
        for strategy in self.strategies:
            curr_videos, curr_audios = strategy.match(
                curr_videos, curr_audios, root_paths, result,
            )

        result.pending_videos.extend(curr_videos)
        result.pending_audios.extend(curr_audios)

        total_saved = len(videos) - len(curr_videos)
        if total_saved > 0:
            logger.info(f"智能配对管线成功配对 {total_saved} 对散流文件")

        return result


def auto_match(
    stream_infos: list[StreamInfo],
    root_paths: list[str],
) -> MatchResult:
    """
    自动配对逻辑（管道入口）
    """
    pipeline = MatcherPipeline()
    return pipeline.execute(stream_infos, root_paths)


def create_manual_task(
    video_info: StreamInfo,
    audio_info: StreamInfo,
    output_name: str,
    root_path: str,
) -> MergeTask:
    """创建手动配对任务"""
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
