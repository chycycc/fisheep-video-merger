"""
功能测试 & 集成测试
覆盖 6 个工具的核心功能 + 服务层 API
"""
import sys
import os
import io
import time

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')
sys.path.insert(0, os.path.join(r'D:\Dev\fisheep-video-merger', 'src'))

TEST_DIR = r'D:\Dev\fisheep-video-merger\test_media'
OUTPUT_DIR = r'D:\Dev\fisheep-video-merger\test_output'
os.makedirs(OUTPUT_DIR, exist_ok=True)

passed = [0]
failed = [0]
errors = []

def check(name, cond, detail=""):
    if cond:
        print(f"  PASS: {name}")
        passed[0] += 1
    else:
        msg = f"  FAIL: {name}" + (f" -- {detail}" if detail else "")
        print(msg)
        failed[0] += 1
        errors.append(name)

def section(title):
    print(f"\n{'='*50}")
    print(f"  {title}")
    print(f"{'='*50}")


# ==========================================
# 准备测试文件
# ==========================================
section("准备测试文件")

video = os.path.join(TEST_DIR, 'test_video.mp4')
srt_a = os.path.join(TEST_DIR, 'test.srt')
srt_b = os.path.join(TEST_DIR, 'test_b.srt')

check("测试视频存在", os.path.exists(video), f"path={video}")
check("测试字幕 A 存在", os.path.exists(srt_a))
check("测试字幕 B 存在", os.path.exists(srt_b))

if not os.path.exists(video):
    print("ERROR: 测试视频不存在，无法继续")
    sys.exit(1)


# ==========================================
# 功能测试 1: 格式转换
# ==========================================
section("功能测试: 格式转换 (converter)")

from fisheep_video_merger.core.converter import convert_single

# 测试 1.1: 流复制模式
out = os.path.join(OUTPUT_DIR, 'converted_copy.mkv')
ok, err = convert_single(video, out, mode='copy')
check("流复制 mp4->mkv", ok and os.path.exists(out), err or "")

# 测试 1.2: 重编码模式
out = os.path.join(OUTPUT_DIR, 'converted_recode.mp4')
ok, err = convert_single(video, out, mode='h264', crf=28, preset='ultrafast')
check("重编码 h264", ok and os.path.exists(out), err or "")

# 测试 1.3: 输出文件大小合理
if os.path.exists(out):
    size = os.path.getsize(out)
    check("输出文件大小 > 0", size > 0, f"size={size}")


# ==========================================
# 功能测试 2: 音频提取
# ==========================================
section("功能测试: 音频提取 (extractor)")

from fisheep_video_merger.core.extractor import extract_audio

# 测试 2.1: 提取 MP3
out = os.path.join(OUTPUT_DIR, 'extracted.mp3')
ok, err = extract_audio(video, out, 'mp3', '128k')
check("提取 MP3", ok and os.path.exists(out), err or "")

# 测试 2.2: 提取 AAC
out = os.path.join(OUTPUT_DIR, 'extracted.m4a')
ok, err = extract_audio(video, out, 'aac', '192k')
check("提取 AAC", ok and os.path.exists(out), err or "")

# 测试 2.3: 提取 FLAC
out = os.path.join(OUTPUT_DIR, 'extracted.flac')
ok, err = extract_audio(video, out, 'flac', '192k')
check("提取 FLAC", ok and os.path.exists(out), err or "")

# 测试 2.4: 提取 WAV
out = os.path.join(OUTPUT_DIR, 'extracted.wav')
ok, err = extract_audio(video, out, 'wav', '192k')
check("提取 WAV", ok and os.path.exists(out), err or "")

# 测试 2.5: 音量调节
out = os.path.join(OUTPUT_DIR, 'extracted_vol.mp3')
ok, err = extract_audio(video, out, 'mp3', '128k', volume=0.5)
check("音量调节 0.5x", ok and os.path.exists(out), err or "")

# 测试 2.6: 声道转换
out = os.path.join(OUTPUT_DIR, 'extracted_mono.mp3')
ok, err = extract_audio(video, out, 'mp3', '128k', channels='mono')
check("转换单声道", ok and os.path.exists(out), err or "")


# ==========================================
# 功能测试 3: 视频压缩
# ==========================================
section("功能测试: 视频压缩 (compressor)")

from fisheep_video_merger.core.compressor import compress_video

# 测试 3.1: 快速压缩
out = os.path.join(OUTPUT_DIR, 'compressed_fast.mp4')
ok, err = compress_video(video, out, preset='fast', resolution='original')
check("快速压缩", ok and os.path.exists(out), err or "")

# 测试 3.2: 均衡压缩 + 降分辨率
out = os.path.join(OUTPUT_DIR, 'compressed_720p.mp4')
ok, err = compress_video(video, out, preset='balanced', resolution='720p')
check("均衡压缩 720p", ok and os.path.exists(out), err or "")

# 测试 3.3: 高质量压缩
out = os.path.join(OUTPUT_DIR, 'compressed_quality.mp4')
ok, err = compress_video(video, out, preset='quality', resolution='original')
check("高质量压缩", ok and os.path.exists(out), err or "")


# ==========================================
# 功能测试 4: 视频裁剪
# ==========================================
section("功能测试: 视频裁剪 (trimmer)")

from fisheep_video_merger.core.trimmer import trim_video

# 测试 4.1: 快速裁剪
out = os.path.join(OUTPUT_DIR, 'trimmed_fast.mp4')
ok, err = trim_video(video, out, '00:00:00', '00:00:02', accurate_mode=False)
check("快速裁剪 0-2s", ok and os.path.exists(out), err or "")

# 测试 4.2: 精确裁剪
out = os.path.join(OUTPUT_DIR, 'trimmed_accurate.mp4')
ok, err = trim_video(video, out, '00:00:01', '00:00:03', accurate_mode=True)
check("精确裁剪 1-3s", ok and os.path.exists(out), err or "")

# 测试 4.3: 秒数格式
out = os.path.join(OUTPUT_DIR, 'trimmed_secs.mp4')
ok, err = trim_video(video, out, '0.5', '2.5', accurate_mode=False)
check("秒数格式 0.5-2.5s", ok and os.path.exists(out), err or "")


# ==========================================
# 功能测试 5: 字幕工具
# ==========================================
section("功能测试: 字幕工具 (subtitle)")

from fisheep_video_merger.core.subtitle import (
    adjust_subtitle, adjust_subtitle_segments, merge_subtitles,
    convert_subtitle, split_bilingual, extract_from_video
)

# 测试 5.1: 整体调轴
out = os.path.join(OUTPUT_DIR, 'adjusted.srt')
ok, err = adjust_subtitle(srt_a, out, 2500)
check("整体调轴 +2.5s", ok and os.path.exists(out), err or "")
if ok:
    content = open(out, encoding='utf-8').read()
    check("调轴后时间戳正确", '00:00:03,000' in content)

# 测试 5.2: 按片段调轴
out = os.path.join(OUTPUT_DIR, 'adjusted_seg.srt')
segments = [{'start_ms': 0, 'end_ms': 2000, 'offset_ms': 1000}]
ok, err = adjust_subtitle_segments(srt_a, out, segments)
check("按片段调轴", ok and os.path.exists(out), err or "")

# 测试 5.3: 格式转换 srt->ass
out = os.path.join(OUTPUT_DIR, 'converted.ass')
ok, err = convert_subtitle(srt_a, out, 'ass')
check("SRT->ASS", ok and os.path.exists(out), err or "")

# 测试 5.4: 格式转换 srt->vtt
out = os.path.join(OUTPUT_DIR, 'converted.vtt')
ok, err = convert_subtitle(srt_a, out, 'vtt')
check("SRT->VTT", ok and os.path.exists(out), err or "")
if ok:
    content = open(out, encoding='utf-8').read()
    check("VTT 包含 WEBVTT", 'WEBVTT' in content)

# 测试 5.5: 字幕合并
out = os.path.join(OUTPUT_DIR, 'merged.srt')
ok, err = merge_subtitles(srt_a, srt_b, out, 'top_bottom')
check("字幕合并 top_bottom", ok and os.path.exists(out), err or "")
if ok:
    content = open(out, encoding='utf-8').read()
    check("合并包含两方内容", 'Hello' in content and 'Bonjour' in content)

# 测试 5.6: 字幕合并 interleave
out = os.path.join(OUTPUT_DIR, 'merged_interleave.srt')
ok, err = merge_subtitles(srt_a, srt_b, out, 'interleave')
check("字幕合并 interleave", ok and os.path.exists(out), err or "")

# 测试 5.7: 字幕合并 vertical（兼容性）
out = os.path.join(OUTPUT_DIR, 'merged_vertical.srt')
ok, err = merge_subtitles(srt_a, srt_b, out, 'vertical')
check("字幕合并 vertical 兼容", ok and os.path.exists(out), err or "")

# 测试 5.8: 拆分双语
out_a = os.path.join(OUTPUT_DIR, 'split_a.srt')
out_b = os.path.join(OUTPUT_DIR, 'split_b.srt')
ok, err = split_bilingual(srt_a, out_a, out_b)
check("拆分双语", ok and os.path.exists(out_a) and os.path.exists(out_b), err or "")

# 测试 5.9: 拆分正则
out_a = os.path.join(OUTPUT_DIR, 'split_regex_a.srt')
out_b = os.path.join(OUTPUT_DIR, 'split_regex_b.srt')
ok, err = split_bilingual(srt_a, out_a, out_b, pattern='World')
check("拆分正则", ok and os.path.exists(out_a) and os.path.exists(out_b), err or "")


# ==========================================
# 集成测试: 服务层 API
# ==========================================
section("集成测试: ToolService API")

from fisheep_video_merger.utils.services.tool_service import ToolService

svc = ToolService()

# 测试 6.1: convert_file
result = svc.convert_file(video, 'mkv', 'copy', OUTPUT_DIR, '')
check("ToolService.convert_file", result['status'] == 'success', str(result))

# 测试 6.2: extract_audio_api
result = svc.extract_audio_api(video, 'mp3', '128k', OUTPUT_DIR, '')
check("ToolService.extract_audio_api", result['status'] == 'success', str(result))

# 测试 6.3: compress_video_api
result = svc.compress_video_api(video, 'fast', 'original', OUTPUT_DIR, '')
check("ToolService.compress_video_api", result['status'] == 'success', str(result))

# 测试 6.4: trim_video_api
result = svc.trim_video_api(video, '00:00:00', '00:00:02', 'copy', OUTPUT_DIR, '')
check("ToolService.trim_video_api(copy)", result['status'] == 'success', str(result))

# 测试 6.5: trim_video_api 精确模式
result = svc.trim_video_api(video, '00:00:00', '00:00:02', 'recode', OUTPUT_DIR, '')
check("ToolService.trim_video_api(recode)", result['status'] == 'success', str(result))

# 测试 6.6: subtitle_adjust_api
result = svc.subtitle_adjust_api(srt_a, 2000.0, OUTPUT_DIR, '')
check("ToolService.subtitle_adjust_api", result['status'] == 'success', str(result))

# 测试 6.7: subtitle_convert_api
result = svc.subtitle_convert_api(srt_a, 'ass', OUTPUT_DIR, '')
check("ToolService.subtitle_convert_api", result['status'] == 'success', str(result))

# 测试 6.8: subtitle_merge_api
result = svc.subtitle_merge_api(srt_a, srt_b, OUTPUT_DIR, '', 'top_bottom')
check("ToolService.subtitle_merge_api", result['status'] == 'success', str(result))

# 测试 6.9: subtitle_split_api
result = svc.subtitle_split_api(srt_a, OUTPUT_DIR, '')
check("ToolService.subtitle_split_api", result['status'] == 'success', str(result))

# 测试 6.10: 文件不存在
result = svc.convert_file('nonexistent.mp4', 'mkv', 'copy', OUTPUT_DIR, '')
check("文件不存在返回 error", result['status'] == 'error')

# 测试 6.11: 冲突解决
result1 = svc.convert_file(video, 'mkv', 'copy', OUTPUT_DIR, 'conflict_test')
result2 = svc.convert_file(video, 'mkv', 'copy', OUTPUT_DIR, 'conflict_test')
check("文件名冲突自动解决", result2['status'] == 'success')


# ==========================================
# 清理
# ==========================================
import shutil
shutil.rmtree(OUTPUT_DIR, ignore_errors=True)
shutil.rmtree(TEST_DIR, ignore_errors=True)

# ==========================================
section("测试结果汇总")
# ==========================================
print(f"\n  通过: {passed[0]}")
print(f"  失败: {failed[0]}")
if errors:
    print(f"\n  失败项:")
    for e in errors:
        print(f"    - {e}")

sys.exit(0 if failed[0] == 0 else 1)
