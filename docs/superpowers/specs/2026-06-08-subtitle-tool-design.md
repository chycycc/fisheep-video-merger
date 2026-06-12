# 字幕工具设计文档

> 版本：v1.0 | 日期：2026-06-08 | 状态：设计确认

## 1. 概述

在 Fisheep 视频工具箱中新增「字幕工具」标签页，提供字幕调轴、合并、格式转换、拆分、从视频提取、批量处理等功能。

**目标用户**：追剧/追番用户、视频创作者、语言学习者——需要偶尔处理字幕但不想学 Aegisub 等专业软件的人。

**差异化**：纯离线、轻量（EXE 体积不变）、现代 UI、专注字幕处理。

## 2. 功能清单

| # | 功能 | 说明 | 核心依赖 |
|---|------|------|---------|
| 1 | 整体调轴 | 所有字幕时间戳 ± 偏移（秒/毫秒） | pysubs2 |
| 2 | 按片段调轴 | 选中行范围单独偏移 | pysubs2 |
| 3 | 字幕合并 | 两个字幕合为双语（上下/左右布局） | pysubs2 |
| 4 | 格式转换 | srt ↔ ass ↔ vtt ↔ ssa | pysubs2 |
| 5 | 拆分双语 | 一个双语字幕拆成两个文件 | pysubs2 |
| 6 | 从视频提取 | FFmpeg 提取内嵌字幕 | FFmpeg |
| 7 | 批量处理 | 对多个文件执行同一操作 | 复用任务队列 |

### 未来规划（暂不实现）

| 功能 | 说明 | 阻塞原因 |
|------|------|---------|
| 波形辅助调轴 | 音频波形可视化，拖动对齐 | 需 scipy（+15MB 体积），待评估 |
| 字幕翻译 | 在线/离线翻译字幕文本 | 依赖复杂，质量不确定 |

## 3. 新增依赖

| 包 | 体积 | 用途 |
|----|------|------|
| pysubs2 | 44KB | 字幕解析/操作/格式转换（纯 Python） |

EXE 体积不变，维持 ~21MB。

## 4. 架构设计

采用方案 A：单模块 + 多 API，和现有工具（converter/extractor/compressor/trimmer）架构完全一致。

### 4.1 核心模块 `core/subtitle.py`

7 个函数，统一接口：

```python
def adjust_subtitle(input_file, output_path, offset_ms, progress_callback=None) -> tuple[bool, Optional[str]]
    """整体调轴：所有事件时间戳 + offset_ms"""

def adjust_subtitle_segments(input_file, output_path, segments, progress_callback=None) -> tuple[bool, Optional[str]]
    """按片段调轴：segments = [(start_line, end_line, offset_ms), ...]"""

def merge_subtitles(file_a, file_b, output_path, layout='top_bottom', progress_callback=None) -> tuple[bool, Optional[str]]
    """合并两个字幕为双语：layout='top_bottom' 或 'left_right'"""

def convert_subtitle(input_file, output_path, target_format, progress_callback=None) -> tuple[bool, Optional[str]]
    """格式转换：srt/ass/vtt/ssa 互转"""

def split_bilingual(input_file, output_path_a, output_path_b, pattern=None, progress_callback=None) -> tuple[bool, Optional[str]]
    """拆分双语字幕：默认按奇偶行拆分，可指定正则"""

def extract_from_video(input_file, output_path, stream_index=0, progress_callback=None) -> tuple[bool, Optional[str]]
    """从视频提取内嵌字幕：FFmpeg -map 0:s:{stream_index}"""
```

每个函数遵循现有模式：
1. 调用 `ensure_output_dir(output_path)` 确保输出目录存在
2. 使用 pysubs2 或 FFmpeg 执行操作
3. 通过 `progress_callback` 报告进度
4. 返回 `(bool, Optional[str])` 表示成功/失败和错误信息

### 4.2 服务层 `utils/services/tool_service.py`

新增 6 个 API 方法，遵循现有模式：

```python
def subtitle_adjust_api(self, input_file, output_path, offset_ms, progress_callback=None)
def subtitle_adjust_segments_api(self, input_file, output_path, segments, progress_callback=None)
def subtitle_merge_api(self, file_a, file_b, output_path, layout, progress_callback=None)
def subtitle_convert_api(self, input_file, output_path, target_format, progress_callback=None)
def subtitle_split_api(self, input_file, output_path_a, output_path_b, pattern, progress_callback=None)
def subtitle_extract_api(self, input_file, output_path, stream_index, progress_callback=None)
```

每个方法：验证输入 → 解析输出路径（默认与源文件同目录）→ 调用 core 函数 → 返回 `{"status", "output_path", "message"}`。

### 4.3 桥接层 `utils/bridge.py`

新增对应的薄桥接方法，注册 `"subtitle"` 到：
- `self.settings["tool_output_dirs"]` → `{"subtitle": ""}`
- `self.settings["tool_settings"]` → `{"subtitle": {"operation": "adjust", "offset_ms": 0, ...}}`

### 4.4 前端模块 `ui/web/js/tools/subtitle.js`

ES 模块，导出 `Subtitle` 对象，包含按操作类型分发的 `start()` 方法。

### 4.5 批量处理

复用现有 `window.runToolTask` 循环机制：JS 层遍历 `window.toolFiles.subtitle` 逐个调用对应桥接方法。

## 5. UI 设计

### 5.1 整体布局

左右结构（和现有工具一致）：左侧导航栏新增「字幕工具」按钮，右侧主工作区显示字幕工具面板。

### 5.2 主工作区结构

```
┌──────────────────────────────────────────────────────┐
│ 📝 字幕工具                                           │
│ 字幕调轴、合并、转换、拆分、提取、批量处理    [📄 添加文件] │
├──────────────────────────────────────────────────────┤
│ [调轴] [合并] [转换] [拆分] [提取] [批量]              │  ← 子功能 Tab
├──────────────────────────────────────────────────────┤
│ （参数面板，随子功能切换）                               │
├──────────────────────────────────────────────────────┤
│ （任务列表，复用 <task-list> 组件）                     │
├──────────────────────────────────────────────────────┤
│                     [🚀 开始 xxx]                     │  ← 操作按钮
└──────────────────────────────────────────────────────┘
```

### 5.3 子功能切换

- 顶部 Tab 栏，用 Alpine.js `x-show` 切换参数面板
- 每个子功能有独立的文件列表（不共享）
- 共享同一个任务列表和操作按钮组件

### 5.4 各子功能参数面板

**调轴**：
- 偏移量输入框（±秒，支持小数如 +2.5）
- 方向选择：所有行 / 前N行 / 后N行
- 行数输入（仅前N行/后N行时显示）

**合并**：
- 双文件选择区（文件 A + 文件 B，中间 ↕ 合并标记）
- 布局：上下双语 / 左右列
- 编码：UTF-8 / GBK / 自动检测

**转换**：
- 目标格式下拉：srt / ass / vtt / ssa

**拆分**：
- 拆分规则：奇偶行（默认）/ 正则表达式
- 正则输入框（选择正则时显示）

**提取**：
- 字幕流选择（ffprobe 检测到多个流时显示下拉）

**批量**：
- 操作选择（复用上面某个子功能的参数）
- 共享文件列表（批量模式下文件列表是共享的）

### 5.5 从视频提取的特殊处理

当用户添加视频文件（.mp4/.mkv 等）时：
1. 自动用 ffprobe 检测可用的字幕流
2. 如果只有一个字幕流，直接提取
3. 如果有多个字幕流，显示下拉让用户选择
4. 提取后自动切换到字幕操作模式

## 6. 文件变更清单

| # | 文件 | 变更类型 | 说明 |
|---|------|---------|------|
| 1 | `requirements.txt` | 修改 | 添加 pysubs2 |
| 2 | `core/subtitle.py` | 新增 | 7 个字幕操作函数 |
| 3 | `utils/services/tool_service.py` | 修改 | 添加 6 个 subtitle API 方法 |
| 4 | `utils/bridge.py` | 修改 | 添加桥接方法 + settings 注册 |
| 5 | `ui/web/js/tools/subtitle.js` | 新增 | JS 工具模块 |
| 6 | `ui/web/js/main.js` | 修改 | 导入 + 路由 + validTools |
| 7 | `ui/web/js/settings.js` | 修改 | toolFiles + 事件绑定 |
| 8 | `ui/web/js/bridge.js` | 修改 | 设置同步 |
| 9 | `ui/web/index.html` | 修改 | 侧栏按钮 + 工具面板 |
| 10 | `ui/web/components/task_list.html` | 修改 | 字幕列定义 |

## 7. 待确认事项

无。
