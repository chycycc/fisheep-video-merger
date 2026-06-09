# 音频工具设计文档

> 日期：2026-06-09
> 版本：v0.8.0+
> 状态：待审阅

## 背景

现有工具标签页中，音频相关功能只有「提取音频」（从视频中提取音轨）。用户需要在音频文件之间互转格式，或直接裁剪音频文件，目前只能借助外部工具。本次新增两个独立标签页填补这一空白。

## 功能一：音频转换

### 定位

独立标签页「音频转换」，音频文件之间互转。输入不限格式（FFmpeg 自动识别），输出支持 8 种格式。

### 后端

新建 `core/audio_converter.py`，核心函数：

```python
def convert_audio(
    input_file: str,
    output_path: str,
    output_format: str = "mp3",
    bitrate: str = "192k",
    channels: str = "original",
    sample_rate: str = "original",
    volume: float = 1.0,
    bitrate_mode: str = "cbr",
    progress_callback=None,
) -> tuple[bool, Optional[str]]:
```

**实现要点**：
- 不需要 `-vn`（输入本身就是音频）
- 不需要流复制判断（都是音频→音频，直接重编码）
- 保留 `-map_metadata 0` 元数据
- 格式编码器映射复用 `extractor.py` 的映射表（mp3→libmp3lame, aac→aac, flac→flac, wav→pcm_s16le, opus→libopus, ogg→libvorbis, m4a→aac, wma→wmav2）
- 支持 CBR/VBR 码率模式
- 支持音量增益（0.5-2.0）

### 前端

新增标签页 `#tool-audio-convert`，UI 控件：
- 输出格式下拉框（MP3/AAC/FLAC/WAV/OPUS/OGG/M4A/WMA）
- 质量预设（高/中/低）
- 码率模式（CBR/VBR）
- 码率选择（64k/128k/192k/256k/320k）
- 声道（原始/立体声/单声道）
- 采样率（原始/8000/11025/22050/44100/48000）
- 音量滑块（0.5-2.0）
- 输出目录 + 输出文件名

### 服务层

- `tool_service.py` 新增 `convert_audio_api` 方法
- `bridge.py` 新增 `convert_audio_api` 桥接方法
- `main.js` Alpine store 新增 `audioConvert` 设置项
- 新建 `js/tools/audio_converter.js` 前端逻辑模块

### 导航

侧栏导航新增「🎵 音频转换」按钮，路由 `#audio-convert`。

---

## 功能二：音频裁剪

### 定位

独立标签页「音频裁剪」，直接裁剪音频文件。输入不限格式，输出支持 8 种格式。

### 后端

新建 `core/audio_trimmer.py`，核心函数：

```python
def trim_audio(
    input_file: str,
    output_path: str,
    start_time: str = "00:00:00",
    end_time: Optional[str] = None,
    accurate_mode: bool = False,
    output_format: str = "",
    bitrate: str = "192k",
    progress_callback=None,
) -> tuple[bool, Optional[str]]:
```

**实现要点**：
- 时间解析复用 `trimmer.py` 的 `parse_time` 函数
- 极速模式：`-ss` 在前，`-c copy` 流复制
- 精准模式：`-ss` 在后，用音频编码器重编码
- 输出格式为空时使用源文件格式
- 非空时使用指定格式，编码器根据格式自动选择
- 保留 `-map_metadata 0` 元数据

### 前端

新增标签页 `#tool-audio-trim`，UI 控件：
- 时间轴（复用现有 trim-timeline 组件，支持拖拽手柄）
- 起止时间输入框
- 裁剪模式下拉框（极速/精准）
- 输出格式下拉框（与源文件相同 / 8 种格式）
- 码率选择（64k/128k/192k/256k/320k）
- 输出目录 + 输出文件名

### 服务层

- `tool_service.py` 新增 `trim_audio_api` 方法
- `bridge.py` 新增 `trim_audio_api` 桥接方法
- `main.js` Alpine store 新增 `audioTrim` 设置项
- 新建 `js/tools/audio_trimmer.js` 前端逻辑模块

### 导航

侧栏导航新增「✂️ 音频裁剪」按钮，路由 `#audio-trim`。

---

## 文件结构

新增文件：
- `src/fisheep_video_merger/core/audio_converter.py` — 音频转换后端
- `src/fisheep_video_merger/core/audio_trimmer.py` — 音频裁剪后端
- `src/fisheep_video_merger/ui/web/js/tools/audio_converter.js` — 音频转换前端
- `src/fisheep_video_merger/ui/web/js/tools/audio_trimmer.js` — 音频裁剪前端

修改文件：
- `src/fisheep_video_merger/ui/web/index.html` — 新增两个标签页 HTML
- `src/fisheep_video_merger/ui/web/js/main.js` — Alpine store 新增设置项
- `src/fisheep_video_merger/utils/services/tool_service.py` — 新增 API 方法
- `src/fisheep_video_merger/utils/bridge.py` — 新增桥接方法

---

## 实现优先级

| 优先级 | 功能 | 原因 |
|--------|------|------|
| P0 | 音频转换 | 基础功能，复用现有模式 |
| P1 | 音频裁剪 | 基础功能，复用现有时间轴组件 |
| P2 | 波形显示+播放预览 | 增强体验，后续迭代 |

---

## 技术约束

- 独立模块，不与现有 `extractor.py` 耦合
- 输入格式不限制，FFmpeg 自动识别
- 代码注释必须使用中文
- 音频转换和裁剪的参数映射可参考 `extractor.py`，但独立实现
