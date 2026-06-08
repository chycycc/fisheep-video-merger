"""
字幕处理模块
支持字幕调轴、合并、格式转换、双语拆分、从视频提取等操作
"""

import os
import re
from typing import Callable, Optional

from fisheep_video_merger.core.ffmpeg_runner import run_ffmpeg, ensure_output_dir, get_ffmpeg_path
from fisheep_video_merger.utils.logger import get_logger

logger = get_logger()


def adjust_subtitle(
    input_file: str,
    output_path: str,
    offset_ms: int,
    progress_callback: Optional[Callable] = None,
) -> tuple[bool, Optional[str]]:
    """
    整体调轴：将字幕所有时间戳偏移指定毫秒数

    Args:
        input_file: 输入字幕文件路径（srt/ass/vtt/ssa）
        output_path: 输出字幕文件路径
        offset_ms: 偏移量（毫秒），正数延后，负数提前
        progress_callback: 进度回调

    Returns:
        (成功标志, 错误信息)
    """
    import pysubs2

    err = ensure_output_dir(output_path)
    if err:
        return False, err

    if progress_callback:
        progress_callback("正在调轴...")

    try:
        subs = pysubs2.load(input_file, encoding="utf-8")
        subs.shift(ms=offset_ms)
        subs.save(output_path, encoding="utf-8")

        if progress_callback:
            progress_callback("调轴完成")

        logger.info(f"字幕调轴成功: {input_file} -> {output_path}, 偏移 {offset_ms}ms")
        return True, None

    except Exception as e:
        err_msg = f"字幕调轴失败: {e}"
        logger.error(err_msg)
        return False, err_msg


def adjust_subtitle_segments(
    input_file: str,
    output_path: str,
    segments: list[dict],
    progress_callback: Optional[Callable] = None,
) -> tuple[bool, Optional[str]]:
    """
    按片段调轴：对字幕的不同时段分别应用不同的时间偏移

    Args:
        input_file: 输入字幕文件路径
        output_path: 输出字幕文件路径
        segments: 片段列表，每个元素为 dict:
            {"start_ms": int, "end_ms": int, "offset_ms": int}
            - start_ms / end_ms: 该段的时间范围（原始时间轴）
            - offset_ms: 该段内字幕的偏移量
        progress_callback: 进度回调

    Returns:
        (成功标志, 错误信息)
    """
    import pysubs2

    err = ensure_output_dir(output_path)
    if err:
        return False, err

    if not segments:
        return False, "未提供调轴片段"

    # 校验片段参数
    required_keys = {"start_ms", "end_ms", "offset_ms"}
    for i, seg in enumerate(segments):
        missing = required_keys - set(seg.keys())
        if missing:
            return False, f"片段 #{i} 缺少必要字段: {', '.join(sorted(missing))}"
        if not isinstance(seg["start_ms"], (int, float)) or not isinstance(seg["end_ms"], (int, float)):
            return False, f"片段 #{i} 的 start_ms/end_ms 必须为数值"
        if seg["start_ms"] > seg["end_ms"]:
            return False, f"片段 #{i} 的 start_ms({seg['start_ms']}) 不能大于 end_ms({seg['end_ms']})"

    if progress_callback:
        progress_callback("正在按片段调轴...")

    try:
        subs = pysubs2.load(input_file, encoding="utf-8")

        for event in subs:
            event_mid = (event.start + event.end) / 2
            for seg in segments:
                start_ms = seg.get("start_ms", 0)
                end_ms = seg.get("end_ms", float("inf"))
                offset_ms = seg.get("offset_ms", 0)
                if start_ms <= event_mid <= end_ms:
                    event.start += offset_ms
                    event.end += offset_ms
                    break

        subs.save(output_path, encoding="utf-8")

        if progress_callback:
            progress_callback("按片段调轴完成")

        logger.info(f"字幕按片段调轴成功: {input_file} -> {output_path}")
        return True, None

    except Exception as e:
        err_msg = f"字幕按片段调轴失败: {e}"
        logger.error(err_msg)
        return False, err_msg


def merge_subtitles(
    file_a: str,
    file_b: str,
    output_path: str,
    layout: str = "top_bottom",
    progress_callback: Optional[Callable] = None,
) -> tuple[bool, Optional[str]]:
    """
    字幕合并：将两条字幕合并为一条双语字幕

    Args:
        file_a: 第一条字幕文件路径（显示在下方/主字幕）
        file_b: 第二条字幕文件路径（显示在上方/副字幕）
        output_path: 输出字幕文件路径
        layout: 布局方式
            - "top_bottom": A 在下 B 在上（默认）
            - "interleave": 按时间顺序交错排列
        progress_callback: 进度回调

    Returns:
        (成功标志, 错误信息)
    """
    import pysubs2

    err = ensure_output_dir(output_path)
    if err:
        return False, err

    if progress_callback:
        progress_callback("正在合并字幕...")

    try:
        subs_a = pysubs2.load(file_a, encoding="utf-8")
        subs_b = pysubs2.load(file_b, encoding="utf-8")

        if layout == "top_bottom":
            # ASS 格式：利用 margin_v 和 layer 控制上下位置
            # 先检测输出格式
            _, ext = os.path.splitext(output_path)
            ext = ext.lower()

            if ext in (".ass", ".ssa"):
                # 主字幕（A）保留在默认位置，副字幕（B）用 \pos 移到顶部
                for event in subs_b:
                    event.text = r"{\an8}" + event.text
                    event.layer = 1
                merged = pysubs2.SSAFile()
                merged.events = list(subs_a.events) + list(subs_b.events)
                # 继承 A 的样式信息
                merged.styles.update(subs_a.styles)
                for name, style in subs_b.styles.items():
                    if name not in merged.styles:
                        merged.styles[name] = style
            else:
                # 非 ASS 格式：简单拼接，B 排在 A 前面（上方）
                merged = pysubs2.SSAFile()
                merged.events = list(subs_b.events) + list(subs_a.events)

        elif layout == "interleave":
            # 交错排列：按时间排序
            merged = pysubs2.SSAFile()
            merged.events = sorted(
                list(subs_a.events) + list(subs_b.events),
                key=lambda e: e.start,
            )
        else:
            return False, f"不支持的布局方式: {layout}"

        merged.save(output_path, encoding="utf-8")

        if progress_callback:
            progress_callback("字幕合并完成")

        logger.info(f"字幕合并成功: {file_a} + {file_b} -> {output_path}")
        return True, None

    except Exception as e:
        err_msg = f"字幕合并失败: {e}"
        logger.error(err_msg)
        return False, err_msg


def convert_subtitle(
    input_file: str,
    output_path: str,
    target_format: str,
    progress_callback: Optional[Callable] = None,
) -> tuple[bool, Optional[str]]:
    """
    字幕格式转换

    Args:
        input_file: 输入字幕文件路径
        output_path: 输出字幕文件路径
        target_format: 目标格式（srt/ass/vtt/ssa）
        progress_callback: 进度回调

    Returns:
        (成功标志, 错误信息)
    """
    import pysubs2

    err = ensure_output_dir(output_path)
    if err:
        return False, err

    # 规范化格式名
    fmt = target_format.lower().lstrip(".")
    supported = {"srt", "ass", "ssa", "vtt"}
    if fmt not in supported:
        return False, f"不支持的目标格式: {target_format}，支持: {', '.join(sorted(supported))}"

    if progress_callback:
        progress_callback("正在转换格式...")

    # 确保 output_path 扩展名与 target_format 一致
    base, _ = os.path.splitext(output_path)
    output_path = f"{base}.{fmt}"

    try:
        subs = pysubs2.load(input_file, encoding="utf-8")
        subs.save(output_path, encoding="utf-8")

        if progress_callback:
            progress_callback("格式转换完成")

        logger.info(f"字幕格式转换成功: {input_file} -> {output_path} ({fmt})")
        return True, None

    except Exception as e:
        err_msg = f"字幕格式转换失败: {e}"
        logger.error(err_msg)
        return False, err_msg


def split_bilingual(
    input_file: str,
    output_path_a: str,
    output_path_b: str,
    pattern: Optional[str] = None,
    progress_callback: Optional[Callable] = None,
) -> tuple[bool, Optional[str]]:
    """
    拆分双语字幕为两条单语字幕

    Args:
        input_file: 输入双语字幕文件路径
        output_path_a: 第一条字幕输出路径（主语言，通常是中文/第一行）
        output_path_b: 第二条字幕输出路径（副语言，通常是英文/第二行）
        pattern: 自定义正则模式，用于匹配副语言行。若为 None 则默认按行拆分。
            匹配到的行归入 B，其余归入 A。
        progress_callback: 进度回调

    Returns:
        (成功标志, 错误信息)
    """
    import pysubs2

    err_a = ensure_output_dir(output_path_a)
    if err_a:
        return False, err_a
    err_b = ensure_output_dir(output_path_b)
    if err_b:
        return False, err_b

    if progress_callback:
        progress_callback("正在拆分双语字幕...")

    try:
        subs = pysubs2.load(input_file, encoding="utf-8")
        subs_a = pysubs2.SSAFile()
        subs_b = pysubs2.SSAFile()

        # 继承样式
        subs_a.styles.update(subs.styles)
        subs_b.styles.update(subs.styles)

        # 编译匹配模式
        lang_pattern = None
        if pattern:
            lang_pattern = re.compile(pattern)

        for event_idx, event in enumerate(subs):
            # 按 \N 分割双语行（pysubs2 内部换行符为 \N）
            lines = event.text.split(r"\N")

            if len(lines) < 2:
                # 单行字幕：同时分配给两条输出
                subs_a.events.append(event.copy())
                subs_b.events.append(event.copy())
                continue

            if lang_pattern:
                # 按正则模式分类，逐行匹配
                lines_a = []
                lines_b = []
                for line in lines:
                    clean = pysubs2.SSAEvent.remove_override_tags(line).strip()
                    if lang_pattern.search(clean):
                        lines_b.append(line)
                    else:
                        lines_a.append(line)
            else:
                # 默认：按事件索引奇偶整体分配（不丢弃任何行）
                # 偶数事件归 A，奇数事件归 B
                if event_idx % 2 == 0:
                    lines_a = list(lines)
                    lines_b = []
                else:
                    lines_a = []
                    lines_b = list(lines)

            if lines_a:
                evt_a = event.copy()
                evt_a.text = r"\N".join(lines_a)
                subs_a.events.append(evt_a)

            if lines_b:
                evt_b = event.copy()
                evt_b.text = r"\N".join(lines_b)
                subs_b.events.append(evt_b)

        subs_a.save(output_path_a, encoding="utf-8")
        subs_b.save(output_path_b, encoding="utf-8")

        if progress_callback:
            progress_callback("双语字幕拆分完成")

        logger.info(f"双语字幕拆分成功: {input_file} -> {output_path_a} + {output_path_b}")
        return True, None

    except Exception as e:
        err_msg = f"双语字幕拆分失败: {e}"
        logger.error(err_msg)
        return False, err_msg


def extract_from_video(
    input_file: str,
    output_path: str,
    stream_index: int = 0,
    progress_callback: Optional[Callable] = None,
) -> tuple[bool, Optional[str]]:
    """
    从视频文件中提取内嵌字幕流

    Args:
        input_file: 输入视频文件路径
        output_path: 输出字幕文件路径（格式由扩展名决定）
        stream_index: 字幕流索引（默认 0，即第一条字幕流）
        progress_callback: 进度回调

    Returns:
        (成功标志, 错误信息)
    """
    err = ensure_output_dir(output_path)
    if err:
        return False, err

    # 字幕流在 FFmpeg 中的映射为 s:索引
    stream_map = f"0:s:{stream_index}"

    cmd = [
        get_ffmpeg_path(),
        "-i", input_file,
        "-map", stream_map,
        "-c:s", "copy",
        "-y", output_path,
    ]

    if progress_callback:
        progress_callback(f"正在提取字幕流 #{stream_index}")

    success, err = run_ffmpeg(cmd, output_path, progress_callback, "提取字幕")

    if success:
        logger.info(f"字幕提取成功: {input_file} -> {output_path}")
    return success, err
