# 音频工具实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 新增「音频转换」和「音频裁剪」两个独立标签页，支持音频文件互转和直接裁剪

**Architecture:** 每个工具独立模块（后端 Python + 前端 JS），复用现有工具模式（tool_service → bridge → FFmpeg）。不与现有 extractor.py 耦合。

**Tech Stack:** Python 3.12 + pywebview + Alpine.js + FFmpeg

**测试说明:** 本项目无自动化测试套件，每个任务完成后通过手动运行验证。

---

### Task 1: 音频转换 — 新增独立标签页

**Files:**
- Create: `src/fisheep_video_merger/core/audio_converter.py`
- Create: `src/fisheep_video_merger/ui/web/js/tools/audio_converter.js`
- Modify: `src/fisheep_video_merger/ui/web/index.html`（新增导航按钮 + 标签页 HTML）
- Modify: `src/fisheep_video_merger/ui/web/js/main.js`（Alpine store + hash 路由）
- Modify: `src/fisheep_video_merger/utils/services/tool_service.py`（新增 API 方法）
- Modify: `src/fisheep_video_merger/utils/bridge.py`（新增桥接方法）

- [ ] **Step 1: 创建后端 audio_converter.py**

新建 `src/fisheep_video_merger/core/audio_converter.py`：

```python
"""
音频转换模块
音频文件之间互转格式
"""

import os
from typing import Callable, Optional

from fisheep_video_merger.core.ffmpeg_runner import run_ffmpeg, ensure_output_dir, get_ffmpeg_path
from fisheep_video_merger.utils.logger import get_logger

logger = get_logger()

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


def convert_audio(
    input_file: str,
    output_path: str,
    output_format: str = "mp3",
    bitrate: str = "192k",
    channels: str = "original",
    sample_rate: str = "original",
    volume: float = 1.0,
    bitrate_mode: str = "cbr",
    progress_callback: Optional[Callable] = None,
) -> tuple[bool, Optional[str]]:
    """
    音频文件格式转换

    Args:
        input_file: 输入音频文件路径
        output_path: 输出文件路径
        output_format: 输出格式（mp3/aac/flac/wav/opus/ogg/m4a/wma）
        bitrate: 音频码率（如 "192k"）
        channels: 声道（"original"/"stereo"/"mono"）
        sample_rate: 采样率（"original"/"44100"/"48000" 等）
        volume: 音量增益（0.5-2.0，1.0 为原始音量）
        bitrate_mode: 码率模式（"cbr"/"vbr"）
        progress_callback: 进度回调

    Returns:
        (成功标志, 错误信息)
    """
    err = ensure_output_dir(output_path)
    if err:
        return False, err

    cmd = [get_ffmpeg_path(), "-i", input_file]

    # 声道设置
    if channels == "mono":
        cmd.extend(["-ac", "1"])
    elif channels == "stereo":
        cmd.extend(["-ac", "2"])

    # 采样率设置
    if sample_rate != "original":
        cmd.extend(["-ar", sample_rate])

    # 音量增益
    if volume != 1.0 and volume > 0:
        cmd.extend(["-af", f"volume={volume}"])

    # 编码器和码率
    codec = _FORMAT_CODEC.get(output_format, "libmp3lame")
    cmd.extend(["-c:a", codec])

    if output_format in _BITRATE_FORMATS:
        if bitrate_mode == "vbr" and output_format == "mp3":
            cmd.extend(["-q:a", "2"])
        elif bitrate_mode == "vbr" and output_format == "opus":
            cmd.extend(["-vbr", "on", "-b:a", bitrate])
        else:
            cmd.extend(["-b:a", bitrate])

    # 容器格式
    if output_format in ("aac", "m4a"):
        cmd.extend(["-f", "mp4"])
    elif output_format in ("opus", "ogg"):
        cmd.extend(["-f", "ogg"])

    # 保留元数据
    cmd.extend(["-map_metadata", "0"])

    # MP4/M4A 流媒体加速
    if output_path.lower().endswith((".mp4", ".m4a")):
        cmd.extend(["-movflags", "+faststart"])

    cmd.extend(["-y", output_path])

    if progress_callback:
        progress_callback(f"正在转换: {os.path.basename(output_path)}")

    return run_ffmpeg(cmd, output_path, progress_callback, "转换")
```

- [ ] **Step 2: 创建前端 audio_converter.js**

新建 `src/fisheep_video_merger/ui/web/js/tools/audio_converter.js`：

```javascript
export const AudioConverter = {
    start: () => {
        const tool = 'audio-convert';
        if (!window.toolFiles || !window.toolFiles[tool] || window.toolFiles[tool].length === 0) {
            window.showToast('当前队列中没有文件', 'warning');
            return;
        }

        const settings = Alpine.store('settings').toolSettings.audioConvert;
        const format = settings.format;
        const bitrate = settings.bitrate;
        const bitrateMode = settings.bitrateMode;
        const channels = settings.channels;
        const sampleRate = settings.sampleRate;
        const volume = parseFloat(settings.volume === 'original' ? '1.0' : settings.volume);

        const outputDir = document.getElementById('audio-convert-output-dir')?.value || '';
        const outputName = settings.outputName.trim();

        const checkedCount = document.querySelectorAll(`#${tool}-tbody .tool-row-cb:checked`).length;
        const selCount = checkedCount || window.toolFiles[tool].length;
        const nameForBatch = selCount === 1 ? outputName : '';

        window.runToolTask(tool, (file) => {
            return window.pywebview.api.convert_audio_api(
                file.filepath, format, bitrate, outputDir, nameForBatch,
                channels, sampleRate, volume, bitrateMode
            );
        });
    }
};
```

- [ ] **Step 3: 在 index.html 添加导航按钮**

在侧栏导航的「提取音频」按钮后面添加：

```html
<button class="nav-btn" data-tool="audio-convert"
        :class="{ 'active': $store.app.currentTool === 'audio-convert' }"
        @click="$store.app.currentTool = 'audio-convert'; window.location.hash = 'audio-convert'">
    <span class="nav-icon">🔄</span>
    <span class="nav-text">音频转换</span>
</button>
```

- [ ] **Step 4: 在 index.html 添加标签页 HTML**

在 `#tool-extract` 标签页后面添加：

```html
<div class="tool-panel" id="tool-audio-convert" :class="{ 'active': $store.app.currentTool === 'audio-convert' }">
    <header class="tool-header">
        <div>
            <h2>音频转换</h2>
            <p class="subtitle">音频文件之间互转格式，支持 8 种输出格式</p>
        </div>
        <div class="header-actions">
            <button class="btn btn-secondary" onclick="selectFilesForTool('audio-convert')">📄 添加文件</button>
        </div>
    </header>

    <div class="tool-options" style="flex-wrap: wrap;">
        <div class="tool-option-group">
            <label>输出格式</label>
            <select id="audio-convert-format" x-model="$store.settings.toolSettings.audioConvert.format" @change="callPython('update_tool_setting', 'audioConvert', 'format', $event.target.value)">
                <option value="mp3">MP3</option>
                <option value="aac">AAC</option>
                <option value="flac">FLAC</option>
                <option value="wav">WAV</option>
                <option value="opus">OPUS</option>
                <option value="ogg">OGG</option>
                <option value="m4a">M4A</option>
                <option value="wma">WMA</option>
            </select>
        </div>
        <div class="tool-option-group">
            <label>码率模式</label>
            <select id="audio-convert-bitrate-mode" x-model="$store.settings.toolSettings.audioConvert.bitrateMode" @change="callPython('update_tool_setting', 'audioConvert', 'bitrateMode', $event.target.value)">
                <option value="cbr">CBR（恒定码率）</option>
                <option value="vbr">VBR（可变码率）</option>
            </select>
        </div>
        <div class="tool-option-group">
            <label>音频码率</label>
            <select id="audio-convert-bitrate" x-model="$store.settings.toolSettings.audioConvert.bitrate" @change="callPython('update_tool_setting', 'audioConvert', 'bitrate', $event.target.value)">
                <option value="64k">64 kbps</option>
                <option value="128k">128 kbps</option>
                <option value="192k" selected>192 kbps</option>
                <option value="256k">256 kbps</option>
                <option value="320k">320 kbps</option>
            </select>
        </div>
        <div class="tool-option-group">
            <label>声道</label>
            <select id="audio-convert-channels" x-model="$store.settings.toolSettings.audioConvert.channels" @change="callPython('update_tool_setting', 'audioConvert', 'channels', $event.target.value)">
                <option value="original">保持原始</option>
                <option value="stereo">立体声</option>
                <option value="mono">单声道</option>
            </select>
        </div>
        <div class="tool-option-group">
            <label>采样率</label>
            <select id="audio-convert-sample-rate" x-model="$store.settings.toolSettings.audioConvert.sampleRate" @change="callPython('update_tool_setting', 'audioConvert', 'sampleRate', $event.target.value)">
                <option value="original">保持原始</option>
                <option value="8000">8000 Hz</option>
                <option value="11025">11025 Hz</option>
                <option value="22050">22050 Hz</option>
                <option value="44100">44100 Hz</option>
                <option value="48000">48000 Hz</option>
            </select>
        </div>
        <div class="tool-option-group" style="flex: 1; min-width: 200px;">
            <label>音量调节 <span id="audio-convert-volume-label" style="color: var(--text-muted);">1.0x</span></label>
            <input type="range" id="audio-convert-volume" x-model="$store.settings.toolSettings.audioConvert.volume" min="0.5" max="2.0" step="0.1" value="1.0"
                   style="width: 100%;"
                   oninput="document.getElementById('audio-convert-volume-label').textContent = this.value + 'x'"
                   @change="callPython('update_tool_setting', 'audioConvert', 'volume', parseFloat($event.target.value))">
        </div>
        <div class="tool-option-group" style="flex: 1;">
            <label>输出目录</label>
            <div style="display: flex; gap: 8px;">
                <input type="text" id="audio-convert-output-dir" placeholder="默认与源文件同目录" readonly style="flex: 1;">
                <button class="mini-action-btn" onclick="selectToolOutputDir('audio-convert')">📂</button>
            </div>
        </div>
        <div class="tool-option-group" style="flex: 1;">
            <label>输出文件名 <span style="color: var(--text-muted); font-weight: normal;">（留空则与源文件同名）</span></label>
            <input type="text" id="audio-convert-output-name" x-model="$store.settings.toolSettings.audioConvert.outputName" placeholder="例如: 转换后的音频">
        </div>
    </div>

    <div x-data="{ localTool: 'audio-convert', actionName: '转换' }">
        <task-list></task-list>
        <action-bar></action-bar>
    </div>
</div>
```

- [ ] **Step 5: 修改 main.js Alpine store 和路由**

在 `toolSettings` 中添加 `audioConvert` 设置项：

```javascript
audioConvert: { format: 'mp3', bitrate: '192k', bitrateMode: 'cbr', channels: 'original', sampleRate: 'original', volume: '1.0', outputName: '' },
```

在 `toolOutputDirs` 中添加：

```javascript
toolOutputDirs: { convert: '', extract: '', compress: '', trim: '', 'audio-convert': '', 'audio-trim': '' },
```

在 `initTabs` 的 `validTools` 数组中添加 `'audio-convert'`：

```javascript
const validTools = ['merge', 'convert', 'extract', 'compress', 'trim', 'audio-convert', 'audio-trim', 'settings'];
```

- [ ] **Step 6: 修改 tool_service.py 新增 API 方法**

在 `ToolService` 类中添加：

```python
def convert_audio_api(self, input_file: str, output_format: str, bitrate: str,
                      output_dir: str = "", output_name: str = "",
                      channels: str = "original", sample_rate: str = "original",
                      volume: float = 1.0, bitrate_mode: str = "cbr",
                      progress_callback=None) -> Dict:
    """音频转换"""
    if not os.path.exists(input_file):
        return {"status": "error", "message": "文件不存在"}

    if not output_dir:
        output_dir = os.path.dirname(input_file)
    if output_name:
        name = os.path.splitext(output_name)[0]
    else:
        name = os.path.splitext(os.path.basename(input_file))[0]
    ext = "m4a" if output_format == "aac" else output_format
    output_path = os.path.join(output_dir, f"{name}.{ext}")
    output_path = self._resolve_conflict(output_path)

    try:
        from fisheep_video_merger.core.audio_converter import convert_audio
        success, err = convert_audio(
            input_file, output_path, output_format, bitrate,
            channels=channels, sample_rate=sample_rate,
            volume=volume, bitrate_mode=bitrate_mode,
            progress_callback=progress_callback
        )
        return {"status": "success" if success else "error", "output_path": output_path, "message": err}
    except Exception as e:
        logger.error(f"音频转换异常: {e}")
        return {"status": "error", "message": str(e)}
```

- [ ] **Step 7: 修改 bridge.py 新增桥接方法**

在 `UIBridge` 类中添加：

```python
def convert_audio_api(self, input_file: str, output_format: str, bitrate: str,
                      output_dir: str = "", output_name: str = "",
                      channels: str = "original", sample_rate: str = "original",
                      volume: float = 1.0, bitrate_mode: str = "cbr") -> Dict:
    """音频转换"""
    return self._tool_svc.convert_audio_api(
        input_file, output_format, bitrate, output_dir, output_name,
        channels, sample_rate, volume, bitrate_mode
    )
```

- [ ] **Step 8: 手动测试**

1. 运行 `PYTHONPATH=src python -m fisheep_video_merger.main_web`
2. 确认侧栏显示「🎵 音频转换」导航按钮
3. 点击进入音频转换标签页
4. 添加一个 MP3 文件，选择 AAC 格式，点击转换
5. 验证输出为 .aac 文件，可正常播放

- [ ] **Step 9: 提交**

```bash
git add src/fisheep_video_merger/core/audio_converter.py src/fisheep_video_merger/ui/web/js/tools/audio_converter.js src/fisheep_video_merger/ui/web/index.html src/fisheep_video_merger/ui/web/js/main.js src/fisheep_video_merger/utils/services/tool_service.py src/fisheep_video_merger/utils/bridge.py
git commit -m "feat(audio-convert): 新增音频转换独立标签页"
```

---

### Task 2: 音频裁剪 — 新增独立标签页

**Files:**
- Create: `src/fisheep_video_merger/core/audio_trimmer.py`
- Create: `src/fisheep_video_merger/ui/web/js/tools/audio_trimmer.js`
- Modify: `src/fisheep_video_merger/ui/web/index.html`（新增导航按钮 + 标签页 HTML）
- Modify: `src/fisheep_video_merger/ui/web/js/main.js`（Alpine store + hash 路由）
- Modify: `src/fisheep_video_merger/utils/services/tool_service.py`（新增 API 方法）
- Modify: `src/fisheep_video_merger/utils/bridge.py`（新增桥接方法）

- [ ] **Step 1: 创建后端 audio_trimmer.py**

新建 `src/fisheep_video_merger/core/audio_trimmer.py`：

```python
"""
音频裁剪模块
按起止时间截取音频片段
"""

import os
from typing import Callable, Optional

from fisheep_video_merger.core.ffmpeg_runner import run_ffmpeg, ensure_output_dir, get_ffmpeg_path
from fisheep_video_merger.core.trimmer import parse_time
from fisheep_video_merger.utils.logger import get_logger

logger = get_logger()

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


def trim_audio(
    input_file: str,
    output_path: str,
    start_time: str = "00:00:00",
    end_time: Optional[str] = None,
    accurate_mode: bool = False,
    output_format: str = "",
    bitrate: str = "192k",
    progress_callback: Optional[Callable] = None,
) -> tuple[bool, Optional[str]]:
    """
    裁剪音频片段

    Args:
        input_file: 输入音频文件路径
        output_path: 输出文件路径
        start_time: 开始时间
        end_time: 结束时间
        accurate_mode: 是否精准模式（重编码）
        output_format: 输出格式（空则使用源文件格式）
        bitrate: 音频码率
        progress_callback: 进度回调

    Returns:
        (成功标志, 错误信息)
    """
    err = ensure_output_dir(output_path)
    if err:
        return False, err

    try:
        start_sec = parse_time(start_time)
    except ValueError as e:
        return False, str(e)

    cmd = [get_ffmpeg_path()]

    # 极速模式：-ss 在前（Input seek）
    if not accurate_mode:
        cmd.extend(["-ss", str(start_sec)])

    cmd.extend(["-i", input_file])

    # 精准模式：-ss 在后（Output seek）
    if accurate_mode:
        cmd.extend(["-ss", str(start_sec)])

    # 结束时间
    if end_time:
        try:
            end_sec = parse_time(end_time)
            trim_duration = end_sec - start_sec
            if trim_duration > 0:
                cmd.extend(["-t", str(trim_duration)])
        except ValueError as e:
            return False, str(e)

    # 编码模式
    if not accurate_mode:
        cmd.extend(["-c", "copy"])
    else:
        # 精准模式：根据输出格式选择编码器
        if output_format:
            codec = _FORMAT_CODEC.get(output_format, "libmp3lame")
        else:
            # 根据源文件扩展名推断
            ext = os.path.splitext(input_file)[1].lower().lstrip(".")
            codec = _FORMAT_CODEC.get(ext, "libmp3lame")
        cmd.extend(["-c:a", codec, "-b:a", bitrate])

    # 容器格式
    if output_format in ("aac", "m4a"):
        cmd.extend(["-f", "mp4"])
    elif output_format in ("opus", "ogg"):
        cmd.extend(["-f", "ogg"])

    # 保留元数据
    cmd.extend(["-map_metadata", "0"])

    # MP4/M4A 流媒体加速
    if output_path.lower().endswith((".mp4", ".m4a")):
        cmd.extend(["-movflags", "+faststart"])

    cmd.extend(["-y", output_path])

    if progress_callback:
        mode_str = "精准" if accurate_mode else "极速"
        progress_callback(f"正在{mode_str}裁剪: {os.path.basename(output_path)}")

    return run_ffmpeg(cmd, output_path, progress_callback, "裁剪")
```

- [ ] **Step 2: 创建前端 audio_trimmer.js**

新建 `src/fisheep_video_merger/ui/web/js/tools/audio_trimmer.js`：

```javascript
export const AudioTrimmer = {
    start: () => {
        const tool = 'audio-trim';
        if (!window.toolFiles || !window.toolFiles[tool] || window.toolFiles[tool].length === 0) {
            window.showToast('当前队列中没有文件', 'warning');
            return;
        }

        const settings = Alpine.store('settings').toolSettings.audioTrim;
        const startTime = settings.start || '00:00:00';
        const endTime = settings.end || '';
        const mode = settings.mode;
        const outputFormat = settings.outputFormat;
        const bitrate = settings.bitrate;

        const outputDir = document.getElementById('audio-trim-output-dir')?.value || '';
        const outputName = settings.outputName.trim();

        const checkedCount = document.querySelectorAll(`#${tool}-tbody .tool-row-cb:checked`).length;
        const selCount = checkedCount || window.toolFiles[tool].length;
        const nameForBatch = selCount === 1 ? outputName : '';

        window.runToolTask(tool, (file) => {
            return window.pywebview.api.trim_audio_api(
                file.filepath, startTime, endTime, mode, outputDir, nameForBatch,
                outputFormat, bitrate
            );
        });
    }
};
```

- [ ] **Step 3: 在 index.html 添加导航按钮**

在「音频转换」按钮后面添加：

```html
<button class="nav-btn" data-tool="audio-trim"
        :class="{ 'active': $store.app.currentTool === 'audio-trim' }"
        @click="$store.app.currentTool = 'audio-trim'; window.location.hash = 'audio-trim'">
    <span class="nav-icon">✂️</span>
    <span class="nav-text">音频裁剪</span>
</button>
```

- [ ] **Step 4: 在 index.html 添加标签页 HTML**

在 `#tool-audio-convert` 标签页后面添加：

```html
<div class="tool-panel" id="tool-audio-trim" :class="{ 'active': $store.app.currentTool === 'audio-trim' }">
    <header class="tool-header">
        <div>
            <h2>音频裁剪</h2>
            <p class="subtitle">按起止时间截取音频片段，支持极速和精准两种模式</p>
        </div>
        <div class="header-actions">
            <button class="btn btn-secondary" onclick="selectFilesForTool('audio-trim')">📄 添加文件</button>
        </div>
    </header>

    <div style="margin-bottom: 16px;">
        <div style="display: flex; gap: 12px; margin-top: 8px;">
            <div style="flex: 1;">
                <label style="font-size: 11px; color: var(--text-muted);">开始时间</label>
                <input type="text" id="audio-trim-start" x-model="$store.settings.toolSettings.audioTrim.start" placeholder="00:00:00" value="00:00:00">
            </div>
            <div style="flex: 1;">
                <label style="font-size: 11px; color: var(--text-muted);">结束时间</label>
                <input type="text" id="audio-trim-end" x-model="$store.settings.toolSettings.audioTrim.end" placeholder="00:05:00">
            </div>
        </div>
    </div>

    <div class="tool-options" style="flex-wrap: wrap;">
        <div class="tool-option-group">
            <label>裁剪模式</label>
            <select id="audio-trim-mode" x-model="$store.settings.toolSettings.audioTrim.mode" @change="callPython('update_tool_setting', 'audioTrim', 'mode', $event.target.value)">
                <option value="copy">快速裁剪（关键帧对齐，无损）</option>
                <option value="recode">精确裁剪（重编码，帧级精度）</option>
            </select>
        </div>
        <div class="tool-option-group">
            <label>输出格式</label>
            <select id="audio-trim-output-format" x-model="$store.settings.toolSettings.audioTrim.outputFormat" @change="callPython('update_tool_setting', 'audioTrim', 'outputFormat', $event.target.value)">
                <option value="">与源文件相同</option>
                <option value="mp3">MP3</option>
                <option value="aac">AAC</option>
                <option value="flac">FLAC</option>
                <option value="wav">WAV</option>
                <option value="opus">OPUS</option>
                <option value="ogg">OGG</option>
                <option value="m4a">M4A</option>
                <option value="wma">WMA</option>
            </select>
        </div>
        <div class="tool-option-group">
            <label>音频码率</label>
            <select id="audio-trim-bitrate" x-model="$store.settings.toolSettings.audioTrim.bitrate" @change="callPython('update_tool_setting', 'audioTrim', 'bitrate', $event.target.value)">
                <option value="64k">64 kbps</option>
                <option value="128k">128 kbps</option>
                <option value="192k" selected>192 kbps</option>
                <option value="256k">256 kbps</option>
                <option value="320k">320 kbps</option>
            </select>
        </div>
        <div class="tool-option-group" style="flex: 1;">
            <label>输出目录</label>
            <div style="display: flex; gap: 8px;">
                <input type="text" id="audio-trim-output-dir" placeholder="默认与源文件同目录" readonly style="flex: 1;">
                <button class="mini-action-btn" onclick="selectToolOutputDir('audio-trim')">📂</button>
            </div>
        </div>
        <div class="tool-option-group" style="flex: 1;">
            <label>输出文件名 <span style="color: var(--text-muted); font-weight: normal;">（留空则自动命名）</span></label>
            <input type="text" id="audio-trim-output-name" x-model="$store.settings.toolSettings.audioTrim.outputName" placeholder="例如: 裁剪后的音频">
        </div>
    </div>

    <div x-data="{ localTool: 'audio-trim', actionName: '裁剪' }">
        <task-list></task-list>
        <action-bar></action-bar>
    </div>
</div>
```

- [ ] **Step 5: 修改 main.js Alpine store**

在 `toolSettings` 中添加 `audioTrim` 设置项：

```javascript
audioTrim: { start: '00:00:00', end: '', mode: 'copy', outputFormat: '', bitrate: '192k', outputName: '' },
```

- [ ] **Step 6: 修改 tool_service.py 新增 API 方法**

在 `ToolService` 类中添加：

```python
def trim_audio_api(self, input_file: str, start_time: str, end_time: str, mode: str,
                   output_dir: str = "", output_name: str = "",
                   output_format: str = "", bitrate: str = "192k",
                   progress_callback=None) -> Dict:
    """音频裁剪"""
    if not os.path.exists(input_file):
        return {"status": "error", "message": "文件不存在"}

    if not output_dir:
        output_dir = os.path.dirname(input_file)
    if output_name:
        name = os.path.splitext(output_name)[0]
    else:
        name = os.path.splitext(os.path.basename(input_file))[0] + "_trimmed"

    if output_format:
        ext = f".{output_format}"
    else:
        ext = os.path.splitext(input_file)[1]
    output_path = os.path.join(output_dir, f"{name}{ext}")
    output_path = self._resolve_conflict(output_path)

    accurate_mode = (mode == "accurate")
    try:
        from fisheep_video_merger.core.audio_trimmer import trim_audio
        success, err = trim_audio(
            input_file, output_path, start_time, end_time,
            accurate_mode=accurate_mode,
            output_format=output_format, bitrate=bitrate,
            progress_callback=progress_callback
        )
        return {"status": "success" if success else "error", "output_path": output_path, "message": err}
    except Exception as e:
        logger.error(f"音频裁剪异常: {e}")
        return {"status": "error", "message": str(e)}
```

- [ ] **Step 7: 修改 bridge.py 新增桥接方法**

在 `UIBridge` 类中添加：

```python
def trim_audio_api(self, input_file: str, start_time: str, end_time: str, mode: str,
                   output_dir: str = "", output_name: str = "",
                   output_format: str = "", bitrate: str = "192k") -> Dict:
    """音频裁剪"""
    return self._tool_svc.trim_audio_api(
        input_file, start_time, end_time, mode, output_dir, output_name,
        output_format, bitrate
    )
```

- [ ] **Step 8: 手动测试**

1. 运行应用，确认侧栏显示「✂️ 音频裁剪」导航按钮
2. 点击进入音频裁剪标签页
3. 添加一个 MP3 文件，设置起止时间（如 00:00:10 到 00:00:30）
4. 选择极速模式，点击裁剪
5. 验证输出文件时长约 20 秒，可正常播放

- [ ] **Step 9: 提交**

```bash
git add src/fisheep_video_merger/core/audio_trimmer.py src/fisheep_video_merger/ui/web/js/tools/audio_trimmer.js src/fisheep_video_merger/ui/web/index.html src/fisheep_video_merger/ui/web/js/main.js src/fisheep_video_merger/utils/services/tool_service.py src/fisheep_video_merger/utils/bridge.py
git commit -m "feat(audio-trim): 新增音频裁剪独立标签页"
```

---

## 备注（未来迭代）

- **波形显示**：使用 Web Audio API 解码音频 → Canvas 绘制波形
- **播放预览**：HTML5 Audio 或 Web Audio API 播放指定位置
- **实时拖拽**：复用现有 trim-timeline 组件，支持拖拽手柄设置起止时间
