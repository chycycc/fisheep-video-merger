# 功能增强实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为 5 个工具标签页补充常用格式和参数，提升工具灵活性

**Architecture:** 后端参数化现有 FFmpeg 命令，前端在对应工具选项区新增控件。每个工具独立修改，互不影响。

**Tech Stack:** Python 3.12 + pywebview + Alpine.js + FFmpeg

**测试说明:** 本项目无自动化测试套件，每个任务完成后通过手动运行验证。

---

### Task 1: 格式转换 — 新增目标格式和编码器

**Files:**
- Modify: `src/fisheep_video_merger/core/converter.py`
- Modify: `src/fisheep_video_merger/ui/web/index.html:349-365`
- Modify: `src/fisheep_video_merger/ui/web/js/main.js:150`

- [ ] **Step 1: 修改后端 converter.py，扩展编码器映射**

在 `converter.py` 的 `convert_single` 函数中，扩展 `mode` 分支支持新编码器：

```python
def convert_single(
    input_file: str,
    output_path: str,
    mode: str = "copy",
    crf: int = 23,
    preset: str = "medium",
    scale: str = "original",
    fps: str = "original",
    progress_callback: Optional[Callable] = None,
) -> tuple[bool, Optional[str]]:
    """转换单个视频文件格式"""
    err = ensure_output_dir(output_path)
    if err:
        return False, err

    cmd = [get_ffmpeg_path(), "-i", input_file]

    if fps != "original" and fps:
        cmd.extend(["-r", fps])

    if scale != "original" and scale:
        scale_map = {"1080p": "1920:-2", "720p": "1280:-2", "480p": "854:-2"}
        scale_val = scale_map.get(scale, scale)
        cmd.extend(["-vf", f"scale={scale_val}"])

    if mode == "copy":
        cmd.extend(["-c", "copy"])
    else:
        # 编码器映射
        codec_map = {
            "h264": "libx264",
            "hevc": "libx265",
            "av1": "libsvtav1",
            "vp9": "libvpx-vp9",
        }
        vcodec = codec_map.get(mode, "libx264")

        # H.264 硬件加速
        if mode == "h264":
            hw_encoder = get_hw_encoder()
            if hw_encoder:
                vcodec = hw_encoder

        cmd.extend(["-c:v", vcodec, "-preset", preset, "-crf", str(crf)])

        # VP9 不支持 -preset，用 -deadline 和 -cpu-used 替代
        if mode == "vp9":
            cmd = [c for c in cmd if c not in ["-preset", preset]]
            deadline_map = {"fast": "good", "medium": "good", "slow": "best"}
            cmd.extend(["-deadline", deadline_map.get(preset, "good"), "-cpu-used", "4"])

        # AV1 用 -crf 替代 -cq
        if mode == "av1":
            pass  # SVT-AV1 支持 -crf

        cmd.extend(["-c:a", "aac", "-b:a", "192k"])

    cmd.extend(["-y", output_path])

    if progress_callback:
        progress_callback(f"正在转换: {os.path.basename(output_path)}")

    return run_ffmpeg(cmd, output_path, progress_callback, "转换")
```

- [ ] **Step 2: 修改前端 index.html，添加格式和编码器选项**

在 `index.html` 的 `#convert-format` select 中添加新选项：

```html
<select id="convert-format" x-model="$store.settings.toolSettings.convert.format" @change="callPython('update_tool_setting', 'convert', 'format', $event.target.value)">
    <option value="mp4">MP4</option>
    <option value="mkv">MKV</option>
    <option value="webm">WebM</option>
    <option value="avi">AVI</option>
    <option value="mov">MOV</option>
    <option value="flv">FLV</option>
    <option value="ts">TS</option>
</select>
```

在 `#convert-mode` select 中添加新编码器选项：

```html
<select id="convert-mode" x-model="$store.settings.toolSettings.convert.mode" @change="callPython('update_tool_setting', 'convert', 'mode', $event.target.value)">
    <option value="copy">快速流复制（无损，秒级）</option>
    <option value="h264">H.264 重编码（兼容性最好）</option>
    <option value="hevc">HEVC 重编码（更小体积）</option>
    <option value="av1">AV1 重编码（最新压缩，速度较慢）</option>
    <option value="vp9">VP9 重编码（YouTube 标准）</option>
</select>
```

- [ ] **Step 3: 修改 Alpine store 默认值**

在 `js/main.js` 的 `toolSettings.convert` 中确认默认值：

```javascript
convert: { format: 'mp4', mode: 'copy', crf: '23', outputName: '' },
```

无需修改，默认值已正确。

- [ ] **Step 4: 手动测试**

1. 运行 `PYTHONPATH=src python -m fisheep_video_merger.main_web`
2. 进入格式转换标签页
3. 确认下拉框显示新增的 MOV/FLV/TS 格式
4. 确认下拉框显示新增的 AV1/VP9 编码器
5. 添加一个 MP4 文件，选择 MOV + H.264，点击转换，验证输出为 .mov 文件
6. 选择 MP4 + AV1，点击转换，验证编码正常（速度较慢属正常）

- [ ] **Step 5: 提交**

```bash
git add src/fisheep_video_merger/core/converter.py src/fisheep_video_merger/ui/web/index.html
git commit -m "feat(convert): 新增 MOV/FLV/TS 格式和 AV1/VP9 编码器"
```

---

### Task 2: 提取音频 — 新增音频格式

**Files:**
- Modify: `src/fisheep_video_merger/core/extractor.py:16-32`
- Modify: `src/fisheep_video_merger/ui/web/index.html:398-404`

- [ ] **Step 1: 修改后端 extractor.py，扩展格式映射**

在 `extractor.py` 顶部扩展映射表：

```python
# 格式到编码器的映射
_FORMAT_CODEC = {
    "mp3": "libmp3lame",
    "aac": "aac",
    "flac": "flac",
    "wav": "pcm_s16le",
    "opus": "libopus",
    "ogg": "libvorbis",
    "m4a": "aac",
    "wma": "wmav2",
}

# 支持码率设置的格式
_BITRATE_FORMATS = {"mp3", "aac", "opus", "ogg", "m4a"}

# 源编码到目标格式的流复制兼容映射
_STREAM_COPY_COMPAT = {
    "mp3": {"mp3"},
    "aac": {"aac", "m4a"},
    "flac": {"flac"},
    "wav": {"wav", "pcm_s16le", "pcm_s24le", "pcm_f32le"},
    "opus": {"opus"},
    "ogg": {"vorbis"},
    "wma": {"wmav2"},
}
```

- [ ] **Step 2: 修改 build_cmd 中的格式输出处理**

在 `build_cmd` 函数中，扩展输出格式判断：

```python
# 原来的：
if audio_format == "aac":
    cmd.extend(["-c:a", "aac"])
    ...
    cmd.extend(["-f", "mp4"])

# 改为：
if audio_format in ("aac", "m4a"):
    cmd.extend(["-c:a", "aac"])
    if bitrate_mode == "vbr":
        cmd.extend(["-q:a", "2"])
    else:
        cmd.extend(["-b:a", bitrate])
    cmd.extend(["-f", "mp4"])
elif audio_format == "opus":
    cmd.extend(["-c:a", "libopus", "-b:a", bitrate])
elif audio_format == "ogg":
    cmd.extend(["-c:a", "libvorbis", "-q:a", "6"])
elif audio_format == "wma":
    cmd.extend(["-c:a", "wmav2", "-b:a", bitrate])
else:
    codec = _FORMAT_CODEC.get(audio_format, "aac")
    cmd.extend(["-c:a", codec])
    if audio_format in _BITRATE_FORMATS:
        if bitrate_mode == "vbr" and audio_format == "mp3":
            cmd.extend(["-q:a", "2"])
        else:
            cmd.extend(["-b:a", bitrate])
```

同时更新流复制分支中的格式判断：

```python
if stream_copy:
    cmd.extend(["-c:a", "copy"])
    if audio_format in ("aac", "m4a"):
        cmd.extend(["-f", "mp4"])
```

- [ ] **Step 3: 修改前端 index.html，添加格式选项**

在 `#extract-format` select 中添加新选项：

```html
<select id="extract-format" x-model="$store.settings.toolSettings.extract.format" @change="callPython('update_tool_setting', 'extract', 'format', $event.target.value)">
    <option value="mp3">MP3</option>
    <option value="aac">AAC</option>
    <option value="flac">FLAC</option>
    <option value="wav">WAV</option>
    <option value="opus">OPUS</option>
    <option value="ogg">OGG</option>
    <option value="m4a">M4A</option>
    <option value="wma">WMA</option>
</select>
```

- [ ] **Step 4: 手动测试**

1. 运行应用，进入提取音频标签页
2. 确认下拉框显示新增的 OPUS/OGG/M4A/WMA 格式
3. 添加一个 MP4 文件，选择 OPUS 格式，点击提取，验证输出为 .opus 文件
4. 选择 OGG 格式，验证输出为 .ogg 文件

- [ ] **Step 5: 提交**

```bash
git add src/fisheep_video_merger/core/extractor.py src/fisheep_video_merger/ui/web/index.html
git commit -m "feat(extract): 新增 OPUS/OGG/M4A/WMA 音频格式"
```

---

### Task 3: 视频压缩 — 新增自定义参数

**Files:**
- Modify: `src/fisheep_video_merger/core/compressor.py`
- Modify: `src/fisheep_video_merger/ui/web/index.html:487-516`
- Modify: `src/fisheep_video_merger/ui/web/js/main.js:152`
- Modify: `src/fisheep_video_merger/utils/services/tool_service.py:79-97`

- [ ] **Step 1: 修改后端 compressor.py，支持新参数**

```python
def compress_video(
    input_file: str,
    output_path: str,
    preset: str = "balanced",
    resolution: str = "original",
    target_size_mb: Optional[float] = None,
    target_bitrate: Optional[str] = None,
    custom_crf: Optional[int] = None,
    audio_codec: str = "aac",
    audio_bitrate: str = "128k",
    audio_copy: bool = True,
    progress_callback: Optional[Callable] = None,
) -> tuple[bool, Optional[str]]:
    """压缩视频文件（支持快速 CRF 与精准 Two-Pass）"""
    err = ensure_output_dir(output_path)
    if err:
        return False, err

    crf, ffmpeg_preset = _PRESETS.get(preset, _PRESETS["balanced"])
    # 自定义 CRF 覆盖预设值
    if custom_crf is not None:
        crf = custom_crf

    scale = _RESOLUTION_SCALE.get(resolution)

    base_cmd = [get_ffmpeg_path(), "-i", input_file]
    if scale:
        base_cmd.extend(["-vf", f"scale={scale}"])

    # 音频参数
    if audio_copy:
        audio_args = ["-c:a", "copy"]
    else:
        audio_codec_map = {
            "aac": "aac",
            "mp3": "libmp3lame",
            "ac3": "ac3",
            "flac": "flac",
        }
        codec = audio_codec_map.get(audio_codec, "aac")
        audio_args = ["-c:a", codec, "-b:a", audio_bitrate]

    hw_encoder = get_hw_encoder()

    if target_size_mb or target_bitrate:
        # Two-Pass 压缩
        try:
            from fisheep_video_merger.utils.ffprobe import get_video_detail
            detail = get_video_detail(input_file)
            if not detail or detail.duration <= 0:
                return False, "无法获取视频时长，Two-Pass 失败"

            if target_size_mb:
                target_total_bitrate = (target_size_mb * 8192) / detail.duration
                audio_bitrate_k = int(audio_bitrate.replace("k", "")) if not audio_copy else 192
                target_video_bitrate = max(100, int(target_total_bitrate - audio_bitrate_k))
            else:
                # 按码率压缩
                target_video_bitrate = int(target_bitrate.replace("k", ""))

            passlog_path = output_path + "_passlog"

            # Pass 1
            cmd_pass1 = base_cmd.copy()
            cmd_pass1.extend([
                "-c:v", "libx264",
                "-b:v", f"{target_video_bitrate}k",
                "-preset", ffmpeg_preset,
                "-pass", "1",
                "-passlogfile", passlog_path,
                "-an", "-f", "null",
                "NUL" if os.name == 'nt' else "/dev/null"
            ])

            if progress_callback:
                progress_callback(f"精准压缩 (1/2): 分析视频源中...")

            success, err_msg = run_ffmpeg(cmd_pass1, output_path, progress_callback, "压缩(Pass-1)")
            if not success:
                return False, err_msg

            # Pass 2
            cmd_pass2 = base_cmd.copy()
            cmd_pass2.extend([
                "-c:v", "libx264",
                "-b:v", f"{target_video_bitrate}k",
                "-preset", ffmpeg_preset,
                "-pass", "2",
                "-passlogfile", passlog_path,
            ])
            cmd_pass2.extend(audio_args)
            cmd_pass2.extend(["-y", output_path])

            if progress_callback:
                progress_callback(f"精准压缩 (2/2): 正在生成文件...")

            success, err_msg = run_ffmpeg(cmd_pass2, output_path, progress_callback, "压缩(Pass-2)")

            for ext in ["-0.log", "-0.log.mbtree"]:
                if os.path.exists(passlog_path + ext):
                    os.remove(passlog_path + ext)

            return success, err_msg

        except Exception as e:
            return False, f"Two-Pass 执行失败: {e}"
    else:
        # 快速 CRF 压缩
        cmd = base_cmd.copy()
        if hw_encoder:
            cmd.extend(["-c:v", hw_encoder, "-cq", str(crf)])
        else:
            cmd.extend(["-c:v", "libx264", "-preset", ffmpeg_preset, "-crf", str(crf)])

        cmd.extend(audio_args)
        cmd.extend(["-y", output_path])

        if progress_callback:
            progress_callback(f"正在压缩: {os.path.basename(output_path)}")

        return run_ffmpeg(cmd, output_path, progress_callback, "压缩")
```

- [ ] **Step 2: 修改 tool_service.py，传递新参数**

修改 `compress_video_api` 方法签名和调用：

```python
def compress_video_api(self, input_file: str, preset: str, resolution: str,
                       output_dir: str = "", output_name: str = "",
                       target_size_mb: float = None, target_bitrate: str = None,
                       custom_crf: int = None,
                       audio_codec: str = "aac", audio_bitrate: str = "128k",
                       audio_copy: bool = True,
                       progress_callback=None) -> Dict:
    """视频压缩"""
    if not os.path.exists(input_file):
        return {"status": "error", "message": "文件不存在"}

    if not output_dir:
        output_dir = os.path.dirname(input_file)
    if output_name:
        name = os.path.splitext(output_name)[0]
    else:
        name = os.path.splitext(os.path.basename(input_file))[0] + "_compressed"
    ext = os.path.splitext(input_file)[1]
    output_path = os.path.join(output_dir, f"{name}{ext}")
    output_path = self._resolve_conflict(output_path)

    success, err = compress_video(
        input_file, output_path, preset, resolution,
        target_size_mb=target_size_mb, target_bitrate=target_bitrate,
        custom_crf=custom_crf,
        audio_codec=audio_codec, audio_bitrate=audio_bitrate,
        audio_copy=audio_copy,
        progress_callback=progress_callback
    )
    return {"status": "success" if success else "error", "output_path": output_path, "message": err}
```

- [ ] **Step 3: 修改前端 index.html，添加新控件**

在压缩工具选项区添加新控件：

```html
<div class="tool-options">
    <div class="tool-option-group">
        <label>压缩模式</label>
        <select id="compress-preset" x-model="$store.settings.toolSettings.compress.preset" @change="callPython('update_tool_setting', 'compress', 'preset', $event.target.value)">
            <option value="fast">⚡ 快速（文件较大，速度最快）</option>
            <option value="balanced" selected>🎯 均衡（推荐）</option>
            <option value="quality">💎 高质量（文件最小，速度最慢）</option>
        </select>
    </div>
    <div class="tool-option-group">
        <label>自定义 CRF <span style="color: var(--text-muted); font-weight: normal;">（留空使用预设值）</span></label>
        <input type="number" id="compress-crf" min="0" max="51" placeholder="0-51，越小质量越高"
               x-model="$store.settings.toolSettings.compress.crf"
               @change="callPython('update_tool_setting', 'compress', 'crf', $event.target.value)">
    </div>
    <div class="tool-option-group">
        <label>分辨率缩放</label>
        <select id="compress-resolution" x-model="$store.settings.toolSettings.compress.resolution" @change="callPython('update_tool_setting', 'compress', 'resolution', $event.target.value)">
            <option value="original" selected>原始分辨率</option>
            <option value="4k">缩放至 4K</option>
            <option value="1080p">缩放至 1080p</option>
            <option value="720p">缩放至 720p</option>
            <option value="480p">缩放至 480p</option>
            <option value="360p">缩放至 360p</option>
        </select>
    </div>
    <div class="tool-option-group">
        <label>目标码率 <span style="color: var(--text-muted); font-weight: normal;">（与目标大小二选一）</span></label>
        <input type="text" id="compress-bitrate" placeholder="例如: 2000k"
               x-model="$store.settings.toolSettings.compress.targetBitrate"
               @change="callPython('update_tool_setting', 'compress', 'target_bitrate', $event.target.value)">
    </div>
    <div class="tool-option-group">
        <label>音频编码</label>
        <select id="compress-audio-codec" x-model="$store.settings.toolSettings.compress.audioCodec" @change="callPython('update_tool_setting', 'compress', 'audio_codec', $event.target.value)">
            <option value="copy">直接复制（不重编码）</option>
            <option value="aac">AAC</option>
            <option value="mp3">MP3</option>
            <option value="ac3">AC3</option>
            <option value="flac">FLAC</option>
        </select>
    </div>
    <div class="tool-option-group">
        <label>音频码率</label>
        <select id="compress-audio-bitrate" x-model="$store.settings.toolSettings.compress.audioBitrate" @change="callPython('update_tool_setting', 'compress', 'audio_bitrate', $event.target.value)">
            <option value="64k">64 kbps</option>
            <option value="128k" selected>128 kbps</option>
            <option value="192k">192 kbps</option>
            <option value="256k">256 kbps</option>
            <option value="320k">320 kbps</option>
        </select>
    </div>
    <div class="tool-option-group" style="flex: 1;">
        <label>输出目录</label>
        <div style="display: flex; gap: 8px;">
            <input type="text" id="compress-output-dir" placeholder="默认与源文件同目录" readonly style="flex: 1;">
            <button class="mini-action-btn" onclick="selectToolOutputDir('compress')">📂</button>
        </div>
    </div>
    <div class="tool-option-group" style="flex: 1;">
        <label>输出文件名 <span style="color: var(--text-muted); font-weight: normal;">（留空则自动命名）</span></label>
        <input type="text" id="compress-output-name" x-model="$store.settings.toolSettings.compress.outputName" placeholder="例如: 压缩后的视频">
    </div>
</div>
```

- [ ] **Step 4: 修改 Alpine store 默认值**

在 `js/main.js` 的 `toolSettings.compress` 中添加新字段：

```javascript
compress: { mode: 'crf', targetSize: '50', targetBitrate: '', preset: 'balanced', resolution: '1080p', crf: '', audioCodec: 'copy', audioBitrate: '128k', outputName: '' },
```

- [ ] **Step 5: 手动测试**

1. 运行应用，进入视频压缩标签页
2. 确认显示新增的 CRF 输入框、4K/360p 分辨率、目标码率、音频编码/码率选项
3. 添加一个 MP4 文件，选择 720p + 均衡预设，点击压缩，验证输出正常
4. 输入自定义 CRF 值（如 18），验证压缩效果

- [ ] **Step 6: 提交**

```bash
git add src/fisheep_video_merger/core/compressor.py src/fisheep_video_merger/utils/services/tool_service.py src/fisheep_video_merger/ui/web/index.html src/fisheep_video_merger/ui/web/js/main.js
git commit -m "feat(compress): 新增自定义CRF、4K/360p分辨率、目标码率、音频编码选择"
```

---

### Task 4: 视频裁剪 — 新增预览、音频控制、输出格式

**Files:**
- Modify: `src/fisheep_video_merger/core/trimmer.py`
- Modify: `src/fisheep_video_merger/utils/services/tool_service.py:99-118`
- Modify: `src/fisheep_video_merger/ui/web/index.html:524-575`

- [ ] **Step 1: 修改后端 trimmer.py，支持新参数**

```python
def trim_video(
    input_file: str,
    output_path: str,
    start_time: str = "00:00:00",
    end_time: Optional[str] = None,
    duration: Optional[float] = None,
    accurate_mode: bool = False,
    keep_audio: bool = True,
    keep_video: bool = True,
    progress_callback: Optional[Callable] = None,
) -> tuple[bool, Optional[str]]:
    """裁剪视频片段（极速关键帧 vs 逐帧精准）"""
    err = ensure_output_dir(output_path)
    if err:
        return False, err

    try:
        start_sec = parse_time(start_time)
    except ValueError as e:
        return False, str(e)

    cmd = [get_ffmpeg_path()]

    if not accurate_mode:
        cmd.extend(["-ss", str(start_sec)])

    cmd.extend(["-i", input_file])

    if accurate_mode:
        cmd.extend(["-ss", str(start_sec)])

    if end_time:
        try:
            end_sec = parse_time(end_time)
            trim_duration = end_sec - start_sec
            if trim_duration > 0:
                cmd.extend(["-t", str(trim_duration)])
        except ValueError as e:
            return False, str(e)
    elif duration:
        cmd.extend(["-t", str(duration)])

    if not accurate_mode:
        cmd.extend(["-c", "copy"])
    else:
        hw_encoder = get_hw_encoder()
        video_codec = hw_encoder if hw_encoder else "libx264"
        cmd.extend(["-c:v", video_codec, "-c:a", "aac"])

    # 音频/视频控制
    if not keep_audio:
        cmd.extend(["-an"])
    if not keep_video:
        cmd.extend(["-vn"])

    cmd.extend(["-y", output_path])

    if progress_callback:
        mode_str = "精准" if accurate_mode else "极速"
        progress_callback(f"正在{mode_str}裁剪: {os.path.basename(output_path)}")

    return run_ffmpeg(cmd, output_path, progress_callback, "裁剪")
```

- [ ] **Step 2: 修改 tool_service.py，传递新参数**

修改 `trim_video_api` 方法：

```python
def trim_video_api(self, input_file: str, start_time: str, end_time: str, mode: str,
                   output_dir: str = "", output_name: str = "",
                   keep_audio: bool = True, keep_video: bool = True,
                   output_format: str = "",
                   progress_callback=None) -> Dict:
    """视频裁剪"""
    if not os.path.exists(input_file):
        return {"status": "error", "message": "文件不存在"}

    if not output_dir:
        output_dir = os.path.dirname(input_file)
    if output_name:
        name = os.path.splitext(output_name)[0]
    else:
        name = os.path.splitext(os.path.basename(input_file))[0] + "_trimmed"

    # 输出格式
    if output_format:
        ext = f".{output_format}"
    else:
        ext = os.path.splitext(input_file)[1]
    output_path = os.path.join(output_dir, f"{name}{ext}")
    output_path = self._resolve_conflict(output_path)

    accurate_mode = (mode == "accurate")
    success, err = trim_video(
        input_file, output_path, start_time, end_time,
        accurate_mode=accurate_mode,
        keep_audio=keep_audio, keep_video=keep_video,
        progress_callback=progress_callback
    )
    return {"status": "success" if success else "error", "output_path": output_path, "message": err}
```

- [ ] **Step 3: 修改前端 index.html，添加新控件**

在裁剪工具选项区添加音频控制和输出格式：

```html
<div class="tool-options">
    <div class="tool-option-group">
        <label>裁剪模式</label>
        <select id="trim-mode" x-model="$store.settings.toolSettings.trim.mode" @change="callPython('update_tool_setting', 'trim', 'mode', $event.target.value)">
            <option value="copy">快速裁剪（关键帧对齐，无损）</option>
            <option value="recode">精确裁剪（重编码，帧级精度）</option>
        </select>
    </div>
    <div class="tool-option-group">
        <label>音频处理</label>
        <select id="trim-audio" x-model="$store.settings.toolSettings.trim.audioMode" @change="callPython('update_tool_setting', 'trim', 'audio_mode', $event.target.value)">
            <option value="keep">保留音频</option>
            <option value="remove">去除音频（仅视频）</option>
            <option value="only">仅保留音频（去除视频）</option>
        </select>
    </div>
    <div class="tool-option-group">
        <label>输出格式</label>
        <select id="trim-output-format" x-model="$store.settings.toolSettings.trim.outputFormat" @change="callPython('update_tool_setting', 'trim', 'output_format', $event.target.value)">
            <option value="">与源文件相同</option>
            <option value="mp4">MP4</option>
            <option value="mkv">MKV</option>
            <option value="ts">TS</option>
            <option value="avi">AVI</option>
        </select>
    </div>
    <div class="tool-option-group" style="flex: 1;">
        <label>输出目录</label>
        <div style="display: flex; gap: 8px;">
            <input type="text" id="trim-output-dir" placeholder="默认与源文件同目录" readonly style="flex: 1;">
            <button class="mini-action-btn" onclick="selectToolOutputDir('trim')">📂</button>
        </div>
    </div>
    <div class="tool-option-group" style="flex: 1;">
        <label>输出文件名 <span style="color: var(--text-muted); font-weight: normal;">（留空则自动命名）</span></label>
        <input type="text" id="trim-output-name" x-model="$store.settings.toolSettings.trim.outputName" placeholder="例如: 裁剪后的视频">
    </div>
</div>
```

- [ ] **Step 4: 修改 Alpine store 默认值**

在 `js/main.js` 的 `toolSettings.trim` 中添加新字段：

```javascript
trim: { start: '00:00:00', end: '', mode: 'recode', accurate: false, audioMode: 'keep', outputFormat: '', outputName: '' }
```

- [ ] **Step 5: 手动测试**

1. 运行应用，进入视频裁剪标签页
2. 确认显示新增的音频处理和输出格式选项
3. 添加一个 MP4 文件，设置起止时间，选择"去除音频"，点击裁剪，验证输出无音频
4. 选择输出格式为 MKV，验证输出为 .mkv 文件

- [ ] **Step 6: 提交**

```bash
git add src/fisheep_video_merger/core/trimmer.py src/fisheep_video_merger/utils/services/tool_service.py src/fisheep_video_merger/ui/web/index.html src/fisheep_video_merger/ui/web/js/main.js
git commit -m "feat(trim): 新增音频控制、输出格式选择"
```

---

### Task 5: 音视频合并 — 新增音频编码和多音轨

**Files:**
- Modify: `src/fisheep_video_merger/core/merger.py`
- Modify: `src/fisheep_video_merger/ui/web/index.html:765-777`
- Modify: `src/fisheep_video_merger/utils/bridge.py`（合并调用处）
- Modify: `src/fisheep_video_merger/ui/web/js/main.js`（设置 store）

- [ ] **Step 1: 修改后端 merger.py，支持音频编码参数**

```python
def build_ffmpeg_command(
    video_file: str,
    audio_file: str,
    output_path: str,
    shortest: bool = False,
    audio_recode: bool = False,
    audio_codec: str = "aac",
    audio_bitrate: str = "192k",
) -> list[str]:
    """构建 ffmpeg 合并命令"""
    cmd = [get_ffmpeg_path()]

    if video_file:
        cmd.extend(["-i", video_file])
    if audio_file:
        cmd.extend(["-i", audio_file])

    if audio_recode:
        codec_map = {
            "aac": "aac",
            "mp3": "libmp3lame",
            "ac3": "ac3",
            "flac": "flac",
        }
        codec = codec_map.get(audio_codec, "aac")
        cmd.extend(["-c:v", "copy", "-c:a", codec, "-b:a", audio_bitrate])
    else:
        cmd.extend(["-c", "copy"])

    if video_file and audio_file:
        cmd.extend(["-map", "0:v:0", "-map", "1:a:0"])
        if shortest:
            cmd.extend(["-shortest"])
    elif video_file:
        cmd.extend(["-map", "0:v:0"])
    elif audio_file:
        cmd.extend(["-map", "0:a:0"])

    cmd.extend(["-map_metadata", "0"])

    if output_path.lower().endswith((".mp4", ".m4a")):
        cmd.extend(["-movflags", "+faststart"])

    cmd.extend(["-y", output_path])
    return cmd
```

- [ ] **Step 2: 修改 merge_single，传递新参数**

```python
def merge_single(
    video_file: str,
    audio_file: str,
    output_path: str,
    shortest: bool = False,
    audio_codec: str = "aac",
    audio_bitrate: str = "192k",
    progress_callback: Optional[Callable[[str], None]] = None,
    process_callback=None,
) -> tuple[bool, Optional[str]]:
    """执行单个合并任务"""
    err = ensure_output_dir(output_path)
    if err:
        return False, err

    cmd = build_ffmpeg_command(
        video_file, audio_file, output_path,
        shortest=shortest, audio_recode=False,
        audio_codec=audio_codec, audio_bitrate=audio_bitrate
    )

    if progress_callback:
        progress_callback(f"正在合并: {os.path.basename(output_path)}")

    success, err_msg = run_ffmpeg(cmd, output_path, progress_callback, "合并", process_callback)

    if not success:
        logger.warning(f"合并流复制失败，触发音频重编码降级重试: {output_path}")
        if progress_callback:
            progress_callback(f"流复制失败，正在进行兼容模式重试: {os.path.basename(output_path)}")
        cmd_fallback = build_ffmpeg_command(
            video_file, audio_file, output_path,
            shortest=shortest, audio_recode=True,
            audio_codec=audio_codec, audio_bitrate=audio_bitrate
        )
        success, err_msg = run_ffmpeg(cmd_fallback, output_path, progress_callback, "合并(降级)", process_callback)

    return success, err_msg
```

- [ ] **Step 3: 修改前端设置页，添加音频编码选项**

在设置页的合并配置区添加：

```html
<div style="display:flex;flex-direction:row;gap:12px;">
    <div class="form-group" style="flex: 1;">
        <label>输出格式</label>
        <select id="merge-format" x-model="$store.settings.outputFormat">
            <option value="mp4">MP4</option>
            <option value="mkv">MKV</option>
        </select>
    </div>
    <div class="form-group" style="flex: 1;">
        <label>并发数</label>
        <input type="number" id="merge-concurrency" min="1" max="8" x-model.number="$store.settings.concurrency">
    </div>
</div>
<div style="display:flex;flex-direction:row;gap:12px;">
    <div class="form-group" style="flex: 1;">
        <label>重编码音频格式</label>
        <select id="merge-audio-codec" x-model="$store.settings.audioCodec">
            <option value="aac">AAC</option>
            <option value="mp3">MP3</option>
            <option value="ac3">AC3</option>
            <option value="flac">FLAC</option>
        </select>
    </div>
    <div class="form-group" style="flex: 1;">
        <label>重编码音频码率</label>
        <select id="merge-audio-bitrate" x-model="$store.settings.audioBitrate">
            <option value="128k">128 kbps</option>
            <option value="192k" selected>192 kbps</option>
            <option value="256k">256 kbps</option>
            <option value="320k">320 kbps</option>
        </select>
    </div>
</div>
```

- [ ] **Step 4: 修改 Alpine store 和 bridge 传递参数**

在 `js/main.js` 的 settings store 中添加：

```javascript
audioCodec: 'aac',
audioBitrate: '192k',
```

在 `bridge.py` 的合并调用处传递新参数（检查所有调用 `merge_single` 的地方）。

- [ ] **Step 5: 手动测试**

1. 运行应用，进入设置页
2. 确认显示新增的重编码音频格式和码率选项
3. 进入合并标签页，添加视频和音频文件，执行合并
4. 在设置中选择 MP3 音频编码，验证降级重试时使用 MP3 编码

- [ ] **Step 6: 提交**

```bash
git add src/fisheep_video_merger/core/merger.py src/fisheep_video_merger/ui/web/index.html src/fisheep_video_merger/ui/web/js/main.js src/fisheep_video_merger/utils/bridge.py
git commit -m "feat(merge): 新增重编码音频格式/码率选择"
```

---

## 备注（未来迭代）

- **音频转换**：独立标签页，音频文件之间互转
- **音频裁剪**：独立标签页，直接裁剪音频文件
- **多音轨合并**：需调整 matcher 配对逻辑，复杂度较高，单独规划
- **裁剪预览**：需在时间点截图，依赖 `extract_screenshot` 支持指定时间点
