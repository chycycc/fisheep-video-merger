"""
通用 FFmpeg 执行器
所有工具（合并、转换、提取、压缩、裁剪）共用的底层执行逻辑
"""

import os
import re
import time
import subprocess
import shutil
from typing import Callable, Optional

from fisheep_video_merger.utils.logger import get_logger

logger = get_logger()

# 硬件加速编码器检测结果缓存
_hw_accel_info: Optional[dict] = None


def detect_hw_accel() -> dict:
    """
    检测可用的硬件加速编码器
    返回 {"encoder": str, "type": str} 或 {"encoder": None, "type": "software"}
    """
    global _hw_accel_info
    if _hw_accel_info is not None:
        return _hw_accel_info

    # 检测顺序：NVENC（NVIDIA）→ QSV（Intel）→ AMF（AMD）
    hw_encoders = [
        ("h264_nvenc", "NVENC", "NVIDIA GPU"),
        ("h264_qsv", "QSV", "Intel Quick Sync"),
        ("h264_amf", "AMF", "AMD GPU"),
    ]

    ffmpeg = get_ffmpeg_path()
    for encoder, hw_type, desc in hw_encoders:
        try:
            result = subprocess.run(
                [ffmpeg, "-hide_banner", "-encoders"],
                capture_output=True, text=True, timeout=5
            )
            if encoder in result.stdout:
                # 进一步验证编码器实际可用
                test_result = subprocess.run(
                    [ffmpeg, "-hide_banner", "-f", "lavfi", "-i",
                     "testsrc=duration=1:size=320x240:rate=1",
                     "-c:v", encoder, "-f", "null", "-"],
                    capture_output=True, timeout=10
                )
                if test_result.returncode == 0:
                    _hw_accel_info = {"encoder": encoder, "type": hw_type, "desc": desc}
                    logger.info(f"检测到硬件加速: {desc} ({encoder})")
                    return _hw_accel_info
        except (subprocess.TimeoutExpired, subprocess.SubprocessError, FileNotFoundError):
            continue

    _hw_accel_info = {"encoder": None, "type": "software", "desc": "软编码"}
    logger.info("未检测到硬件加速，使用软编码")
    return _hw_accel_info


def get_hw_encoder() -> Optional[str]:
    """获取可用的硬件加速编码器名称，无则返回 None"""
    return detect_hw_accel().get("encoder")

# 进度回调节流间隔（秒）
PROGRESS_THROTTLE_SECONDS = 0.3
# 进度显示最大百分比
MAX_DISPLAY_PERCENT = 99.9
# stderr 读取缓冲大小（字节）
STDERR_CHUNK_SIZE = 4096
# 进程退出等待超时（秒）
FFMPEG_WAIT_TIMEOUT = 30
# 强制终止后等待超时（秒）
FFMPEG_KILL_TIMEOUT = 10
# 错误信息尾部保留行数
ERROR_TAIL_LINES = 5
# 错误信息最大长度（字符）
MAX_ERROR_LENGTH = 500

# FFmpeg 路径缓存
_ffmpeg_path: Optional[str] = None


def get_ffmpeg_path() -> str:
    """获取 ffmpeg 可执行文件路径（带缓存）"""
    global _ffmpeg_path
    if _ffmpeg_path is not None:
        return _ffmpeg_path
    path = shutil.which("ffmpeg")
    _ffmpeg_path = path if path else "ffmpeg"
    return _ffmpeg_path


def run_ffmpeg(
    cmd: list[str],
    output_path: str,
    progress_callback: Optional[Callable] = None,
    op_name: str = "处理",
    process_callback: Optional[Callable[[subprocess.Popen], None]] = None,
) -> tuple[bool, Optional[str]]:
    """
    通用 FFmpeg 执行器，支持实时进度解析和回调

    Args:
        cmd: ffmpeg 命令参数列表
        output_path: 输出文件路径（用于日志和进度显示）
        progress_callback: 进度回调，支持两种签名：
            - callback(text) 仅文本
            - callback(text, percent, eta_sec, speed_mult) 完整信息
        op_name: 操作名称（如 "合并"、"转换"、"提取"）

    Returns:
        (成功标志, 错误信息)
    """
    filename = os.path.basename(output_path)
    duration_regex = re.compile(r"Duration:\s*(\d{2}):(\d{2}):(\d{2})\.(\d{2})")
    time_regex = re.compile(r"time=\s*(\d{2}):(\d{2}):(\d{2})\.(\d{2})")

    def to_seconds(match) -> float:
        h, m, s, ms = match.groups()
        return int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 100.0

    total_seconds = 0.0
    full_stderr = []
    last_emit_time = 0.0
    start_time = time.time()

    logger.info(f"开始执行 ffmpeg {op_name}: {' '.join(cmd)}")

    try:
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            shell=False,
            text=True,
            encoding="utf-8",
            errors="replace",
        )

        if process_callback:
            process_callback(process)

        # 缓冲读取 stderr，按 \r 和 \n 分割
        buffer = ""
        while True:
            chunk = process.stderr.read(STDERR_CHUNK_SIZE)
            if not chunk:
                break
            buffer += chunk

            while "\r" in buffer or "\n" in buffer:
                cr_pos = buffer.find("\r")
                nl_pos = buffer.find("\n")
                if cr_pos == -1:
                    sep_pos = nl_pos
                elif nl_pos == -1:
                    sep_pos = cr_pos
                else:
                    sep_pos = min(cr_pos, nl_pos)

                line = buffer[:sep_pos].strip()
                sep_end = sep_pos + 1
                if sep_pos < len(buffer) - 1 and buffer[sep_pos:sep_pos + 2] == "\r\n":
                    sep_end = sep_pos + 2
                buffer = buffer[sep_end:]

                if not line:
                    continue

                full_stderr.append(line)

                # 匹配总时长
                if total_seconds == 0.0:
                    dur_match = duration_regex.search(line)
                    if dur_match:
                        total_seconds = to_seconds(dur_match)

                # 匹配当前进度
                if total_seconds > 0.0:
                    t_match = time_regex.search(line)
                    if t_match:
                        curr = to_seconds(t_match)
                        pct = min(MAX_DISPLAY_PERCENT, (curr / total_seconds) * 100.0)
                        now = time.time()

                        elapsed = now - start_time
                        speed_mult = (curr / elapsed) if elapsed > 0 else 1.0
                        eta_sec = max(0.0, total_seconds - curr) / speed_mult if speed_mult > 0 else 0.0

                        if (now - last_emit_time >= PROGRESS_THROTTLE_SECONDS) or pct >= MAX_DISPLAY_PERCENT:
                            if progress_callback:
                                txt = f"正在{op_name}: {filename} ({pct:.1f}%)"
                                try:
                                    progress_callback(txt, pct, eta_sec, speed_mult)
                                except TypeError:
                                    try:
                                        progress_callback(txt)
                                    except Exception:
                                        pass
                            last_emit_time = now

        # 处理 buffer 剩余内容
        if buffer.strip():
            full_stderr.append(buffer.strip())

        # 等待进程退出
        process.wait(timeout=FFMPEG_WAIT_TIMEOUT)

        if process.returncode == 0:
            logger.info(f"{op_name}成功: {output_path}")
            return True, None
        else:
            tail = "\n".join(full_stderr[-ERROR_TAIL_LINES:])
            logger.error(f"{op_name}失败: {output_path}\n{tail}")
            return False, tail[:MAX_ERROR_LENGTH]

    except subprocess.TimeoutExpired:
        try:
            process.kill()
            process.wait(timeout=FFMPEG_KILL_TIMEOUT)
        except Exception:
            pass
        return False, f"ffmpeg {op_name}超时"
    except Exception as e:
        logger.error(f"{op_name}执行异常: {e}")
        try:
            process.kill()
            process.wait(timeout=FFMPEG_KILL_TIMEOUT)
        except Exception:
            pass
        return False, str(e)


def ensure_output_dir(output_path: str) -> Optional[str]:
    """确保输出目录存在，返回错误信息或 None"""
    output_dir = os.path.dirname(output_path)
    try:
        os.makedirs(output_dir, exist_ok=True)
        return None
    except OSError as e:
        return f"创建输出目录失败: {e}"
