# 字幕工具实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 Fisheep 视频工具箱中新增「字幕工具」标签页，支持字幕调轴、合并、格式转换、拆分、从视频提取、批量处理。

**Architecture:** 遵循现有工具架构（converter/extractor/compressor/trimmer）的 5 层模式：core 模块 → tool_service → bridge → JS tool → HTML。核心字幕操作使用 pysubs2 库，从视频提取字幕使用 FFmpeg。

**Tech Stack:** Python 3.12, pysubs2, FFmpeg, Alpine.js, pywebview

---

## 文件结构

| 文件 | 职责 |
|------|------|
| `requirements.txt` | 新增 pysubs2 依赖 |
| `src/fisheep_video_merger/core/subtitle.py` | 7 个字幕操作纯函数 |
| `src/fisheep_video_merger/utils/services/tool_service.py` | 6 个 subtitle API 方法 |
| `src/fisheep_video_merger/utils/bridge.py` | 桥接方法 + settings 注册 |
| `src/fisheep_video_merger/ui/web/js/tools/subtitle.js` | JS 工具模块 |
| `src/fisheep_video_merger/ui/web/js/main.js` | 导入 + 路由 + Alpine store |
| `src/fisheep_video_merger/ui/web/js/settings.js` | toolFiles + 事件绑定 |
| `src/fisheep_video_merger/ui/web/js/bridge.js` | 设置同步 |
| `src/fisheep_video_merger/ui/web/index.html` | 侧栏按钮 + 工具面板 |
| `src/fisheep_video_merger/ui/web/components/task_list.html` | 字幕列定义 |

---

### Task 1: 安装 pysubs2 依赖

**Files:**
- Modify: `requirements.txt`

- [ ] **Step 1: 添加 pysubs2 到 requirements.txt**

```txt
send2trash
pywebview==6.2.1
pysubs2
```

- [ ] **Step 2: 安装依赖**

Run: `pip install pysubs2`
Expected: Successfully installed pysubs2-1.8.1

- [ ] **Step 3: 验证安装**

Run: `python -c "import pysubs2; print(pysubs2.__version__)"`
Expected: 1.8.1 (或类似版本号)

- [ ] **Step 4: 提交**

```bash
git add requirements.txt
git commit -m "feat(subtitle): 添加 pysubs2 依赖"
```

---

### Task 2: 创建核心模块 `core/subtitle.py`

**Files:**
- Create: `src/fisheep_video_merger/core/subtitle.py`

- [ ] **Step 1: 创建文件，写入整体调轴函数**

```python
"""
字幕工具模块
支持字幕调轴、合并、格式转换、拆分、从视频提取
"""

import os
from typing import Callable, Optional

import pysubs2

from fisheep_video_merger.core.ffmpeg_runner import ensure_output_dir, get_ffmpeg_path, run_ffmpeg


def adjust_subtitle(
    input_file: str,
    output_path: str,
    offset_ms: float,
    progress_callback: Optional[Callable] = None,
) -> tuple[bool, Optional[str]]:
    """整体调轴：所有事件时间戳 + offset_ms（毫秒）"""
    err = ensure_output_dir(output_path)
    if err:
        return False, err

    try:
        subs = pysubs2.load(input_file)
        for event in subs.events:
            event.start += int(offset_ms)
            event.end += int(offset_ms)
        subs.save(output_path)
        return True, None
    except Exception as e:
        return False, f"调轴失败: {e}"
```

- [ ] **Step 2: 添加按片段调轴函数**

在文件末尾追加：

```python
def adjust_subtitle_segments(
    input_file: str,
    output_path: str,
    segments: list,
    progress_callback: Optional[Callable] = None,
) -> tuple[bool, Optional[str]]:
    """
    按片段调轴：对指定行范围做偏移
    segments: [(start_line, end_line, offset_ms), ...]，行号从 1 开始
    """
    err = ensure_output_dir(output_path)
    if err:
        return False, err

    try:
        subs = pysubs2.load(input_file)
        for start_line, end_line, offset_ms in segments:
            for i in range(start_line - 1, min(end_line, len(subs.events))):
                subs.events[i].start += int(offset_ms)
                subs.events[i].end += int(offset_ms)
        subs.save(output_path)
        return True, None
    except Exception as e:
        return False, f"按片段调轴失败: {e}"
```

- [ ] **Step 3: 添加字幕合并函数**

```python
def merge_subtitles(
    file_a: str,
    file_b: str,
    output_path: str,
    layout: str = "top_bottom",
    progress_callback: Optional[Callable] = None,
) -> tuple[bool, Optional[str]]:
    """合并两个字幕为双语字幕。layout: 'top_bottom' 或 'left_right'"""
    err = ensure_output_dir(output_path)
    if err:
        return False, err

    try:
        subs_a = pysubs2.load(file_a)
        subs_b = pysubs2.load(file_b)

        # 合并事件列表
        merged = pysubs2.SSAFile()
        merged.info = subs_a.info.copy()
        merged.styles = subs_a.styles.copy()

        for event in subs_a.events:
            merged.events.append(event)

        for event in subs_b.events:
            # 副字幕添加偏移样式
            new_event = event.copy()
            if layout == "top_bottom":
                new_event.style = "Secondary"
                if "Secondary" not in merged.styles:
                    style = subs_b.styles.get(event.style, pysubs2.SSAStyle())
                    new_style = style.copy()
                    new_style.alignment = 2  # 底部左对齐
                    merged.styles["Secondary"] = new_style
            merged.events.append(new_event)

        merged.save(output_path)
        return True, None
    except Exception as e:
        return False, f"合并失败: {e}"
```

- [ ] **Step 4: 添加格式转换函数**

```python
def convert_subtitle(
    input_file: str,
    output_path: str,
    target_format: str,
    progress_callback: Optional[Callable] = None,
) -> tuple[bool, Optional[str]]:
    """格式转换：srt/ass/vtt/ssa 互转"""
    err = ensure_output_dir(output_path)
    if err:
        return False, err

    try:
        subs = pysubs2.load(input_file)
        subs.save(output_path)
        return True, None
    except Exception as e:
        return False, f"格式转换失败: {e}"
```

- [ ] **Step 5: 添加拆分双语函数**

```python
def split_bilingual(
    input_file: str,
    output_path_a: str,
    output_path_b: str,
    pattern: Optional[str] = None,
    progress_callback: Optional[Callable] = None,
) -> tuple[bool, Optional[str]]:
    """拆分双语字幕为两个独立文件。默认按奇偶行拆分。"""
    err_a = ensure_output_dir(output_path_a)
    err_b = ensure_output_dir(output_path_b)
    if err_a:
        return False, err_a
    if err_b:
        return False, err_b

    try:
        subs = pysubs2.load(input_file)
        subs_a = pysubs2.SSAFile()
        subs_b = pysubs2.SSAFile()
        subs_a.info = subs.info.copy()
        subs_b.info = subs.info.copy()
        subs_a.styles = subs.styles.copy()
        subs_b.styles = subs.styles.copy()

        if pattern:
            import re
            regex = re.compile(pattern)
            for event in subs.events:
                if regex.search(event.text):
                    subs_b.events.append(event)
                else:
                    subs_a.events.append(event)
        else:
            # 默认按奇偶行拆分
            for i, event in enumerate(subs.events):
                if i % 2 == 0:
                    subs_a.events.append(event)
                else:
                    subs_b.events.append(event)

        subs_a.save(output_path_a)
        subs_b.save(output_path_b)
        return True, None
    except Exception as e:
        return False, f"拆分失败: {e}"
```

- [ ] **Step 6: 添加从视频提取字幕函数**

```python
def extract_from_video(
    input_file: str,
    output_path: str,
    stream_index: int = 0,
    progress_callback: Optional[Callable] = None,
) -> tuple[bool, Optional[str]]:
    """从视频提取内嵌字幕"""
    err = ensure_output_dir(output_path)
    if err:
        return False, err

    cmd = [
        get_ffmpeg_path(),
        "-i", input_file,
        "-map", f"0:s:{stream_index}",
        "-y", output_path,
    ]

    if progress_callback:
        progress_callback(f"正在提取字幕: {os.path.basename(output_path)}")

    return run_ffmpeg(cmd, output_path, progress_callback, "提取字幕")
```

- [ ] **Step 7: 提交**

```bash
git add src/fisheep_video_merger/core/subtitle.py
git commit -m "feat(subtitle): 创建核心模块，实现 6 个字幕操作函数"
```

---

### Task 3: 添加服务层方法 `tool_service.py`

**Files:**
- Modify: `src/fisheep_video_merger/utils/services/tool_service.py`

- [ ] **Step 1: 添加 import**

在文件顶部 import 区域添加：

```python
from fisheep_video_merger.core.subtitle import (
    adjust_subtitle,
    adjust_subtitle_segments,
    merge_subtitles,
    convert_subtitle,
    split_bilingual,
    extract_from_video,
)
```

- [ ] **Step 2: 添加 subtitle_adjust_api 方法**

在 `trim_video_api` 方法之后追加：

```python
def subtitle_adjust_api(self, input_file: str, offset_ms: float,
                        output_dir: str = "", output_name: str = "",
                        progress_callback=None) -> Dict:
    """字幕整体调轴"""
    if not os.path.exists(input_file):
        return {"status": "error", "message": "文件不存在"}

    if not output_dir:
        output_dir = os.path.dirname(input_file)
    if output_name:
        name = os.path.splitext(output_name)[0]
    else:
        name = os.path.splitext(os.path.basename(input_file))[0]
    ext = os.path.splitext(input_file)[1]
    output_path = os.path.join(output_dir, f"{name}_adjusted{ext}")
    output_path = self._resolve_conflict(output_path)

    try:
        success, err = adjust_subtitle(input_file, output_path, offset_ms, progress_callback)
        return {"status": "success" if success else "error", "output_path": output_path, "message": err}
    except Exception as e:
        logger.error(f"字幕调轴异常: {e}")
        return {"status": "error", "message": str(e)}
```

- [ ] **Step 3: 添加 subtitle_adjust_segments_api 方法**

```python
def subtitle_adjust_segments_api(self, input_file: str, segments: list,
                                 output_dir: str = "", output_name: str = "",
                                 progress_callback=None) -> Dict:
    """字幕按片段调轴"""
    if not os.path.exists(input_file):
        return {"status": "error", "message": "文件不存在"}

    if not output_dir:
        output_dir = os.path.dirname(input_file)
    if output_name:
        name = os.path.splitext(output_name)[0]
    else:
        name = os.path.splitext(os.path.basename(input_file))[0]
    ext = os.path.splitext(input_file)[1]
    output_path = os.path.join(output_dir, f"{name}_adjusted{ext}")
    output_path = self._resolve_conflict(output_path)

    try:
        success, err = adjust_subtitle_segments(input_file, output_path, segments, progress_callback)
        return {"status": "success" if success else "error", "output_path": output_path, "message": err}
    except Exception as e:
        logger.error(f"字幕按片段调轴异常: {e}")
        return {"status": "error", "message": str(e)}
```

- [ ] **Step 4: 添加 subtitle_merge_api 方法**

```python
def subtitle_merge_api(self, file_a: str, file_b: str,
                       output_dir: str = "", output_name: str = "",
                       layout: str = "top_bottom",
                       progress_callback=None) -> Dict:
    """字幕合并"""
    if not os.path.exists(file_a):
        return {"status": "error", "message": "文件 A 不存在"}
    if not os.path.exists(file_b):
        return {"status": "error", "message": "文件 B 不存在"}

    if not output_dir:
        output_dir = os.path.dirname(file_a)
    if output_name:
        name = os.path.splitext(output_name)[0]
    else:
        name = os.path.splitext(os.path.basename(file_a))[0] + "_merged"
    ext = os.path.splitext(file_a)[1]
    output_path = os.path.join(output_dir, f"{name}{ext}")
    output_path = self._resolve_conflict(output_path)

    try:
        success, err = merge_subtitles(file_a, file_b, output_path, layout, progress_callback)
        return {"status": "success" if success else "error", "output_path": output_path, "message": err}
    except Exception as e:
        logger.error(f"字幕合并异常: {e}")
        return {"status": "error", "message": str(e)}
```

- [ ] **Step 5: 添加 subtitle_convert_api 方法**

```python
def subtitle_convert_api(self, input_file: str, target_format: str,
                         output_dir: str = "", output_name: str = "",
                         progress_callback=None) -> Dict:
    """字幕格式转换"""
    if not os.path.exists(input_file):
        return {"status": "error", "message": "文件不存在"}

    if not output_dir:
        output_dir = os.path.dirname(input_file)
    if output_name:
        name = os.path.splitext(output_name)[0]
    else:
        name = os.path.splitext(os.path.basename(input_file))[0]
    output_path = os.path.join(output_dir, f"{name}.{target_format}")
    output_path = self._resolve_conflict(output_path)

    try:
        success, err = convert_subtitle(input_file, output_path, target_format, progress_callback)
        return {"status": "success" if success else "error", "output_path": output_path, "message": err}
    except Exception as e:
        logger.error(f"字幕格式转换异常: {e}")
        return {"status": "error", "message": str(e)}
```

- [ ] **Step 6: 添加 subtitle_split_api 方法**

```python
def subtitle_split_api(self, input_file: str,
                       output_dir: str = "", output_name: str = "",
                       pattern: Optional[str] = None,
                       progress_callback=None) -> Dict:
    """拆分双语字幕"""
    if not os.path.exists(input_file):
        return {"status": "error", "message": "文件不存在"}

    if not output_dir:
        output_dir = os.path.dirname(input_file)
    if output_name:
        name = os.path.splitext(output_name)[0]
    else:
        name = os.path.splitext(os.path.basename(input_file))[0]
    ext = os.path.splitext(input_file)[1]
    output_path_a = os.path.join(output_dir, f"{name}_A{ext}")
    output_path_b = os.path.join(output_dir, f"{name}_B{ext}")
    output_path_a = self._resolve_conflict(output_path_a)
    output_path_b = self._resolve_conflict(output_path_b)

    try:
        success, err = split_bilingual(input_file, output_path_a, output_path_b, pattern, progress_callback)
        result_path = f"{output_path_a};{output_path_b}" if success else ""
        return {"status": "success" if success else "error", "output_path": result_path, "message": err}
    except Exception as e:
        logger.error(f"字幕拆分异常: {e}")
        return {"status": "error", "message": str(e)}
```

- [ ] **Step 7: 添加 subtitle_extract_api 方法**

```python
def subtitle_extract_api(self, input_file: str,
                         output_dir: str = "", output_name: str = "",
                         stream_index: int = 0,
                         output_format: str = "srt",
                         progress_callback=None) -> Dict:
    """从视频提取内嵌字幕"""
    if not os.path.exists(input_file):
        return {"status": "error", "message": "文件不存在"}

    if not output_dir:
        output_dir = os.path.dirname(input_file)
    if output_name:
        name = os.path.splitext(output_name)[0]
    else:
        name = os.path.splitext(os.path.basename(input_file))[0]
    output_path = os.path.join(output_dir, f"{name}.{output_format}")
    output_path = self._resolve_conflict(output_path)

    try:
        success, err = extract_from_video(input_file, output_path, stream_index, progress_callback)
        return {"status": "success" if success else "error", "output_path": output_path, "message": err}
    except Exception as e:
        logger.error(f"提取字幕异常: {e}")
        return {"status": "error", "message": str(e)}
```

- [ ] **Step 8: 提交**

```bash
git add src/fisheep_video_merger/utils/services/tool_service.py
git commit -m "feat(subtitle): 添加 6 个字幕服务层 API 方法"
```

---

### Task 4: 添加桥接方法 `bridge.py`

**Files:**
- Modify: `src/fisheep_video_merger/utils/bridge.py`

- [ ] **Step 1: 注册 settings**

在 `__init__` 的 `self.settings` 字典中，`tool_output_dirs` 添加 `"subtitle": ""`，`tool_settings` 添加 `"subtitle": {"operation": "adjust", "offset_ms": 0, "layout": "top_bottom"}`。

```python
"tool_output_dirs": {"convert": "", "extract": "", "compress": "", "trim": "", "subtitle": ""},
"tool_settings": {
    "convert": {"format": "mp4", "mode": "copy"},
    "extract": {"format": "aac", "bitrate": "192k"},
    "compress": {"preset": "balanced", "resolution": "720p"},
    "trim": {"mode": "reencode"},
    "subtitle": {"operation": "adjust", "offset_ms": 0, "layout": "top_bottom"},
},
```

- [ ] **Step 2: 添加桥接方法**

在 `trim_video_api` 方法之后追加：

```python
def subtitle_adjust_api(self, input_file: str, offset_ms: float,
                        output_dir: str = "", output_name: str = "") -> Dict:
    if not output_dir:
        output_dir = self.settings.get("output_dir") or os.path.dirname(input_file)
    return self._tool_svc.subtitle_adjust_api(
        input_file, offset_ms, output_dir, output_name,
        self._make_tool_progress_callback('subtitle')
    )

def subtitle_adjust_segments_api(self, input_file: str, segments: list,
                                 output_dir: str = "", output_name: str = "") -> Dict:
    if not output_dir:
        output_dir = self.settings.get("output_dir") or os.path.dirname(input_file)
    return self._tool_svc.subtitle_adjust_segments_api(
        input_file, segments, output_dir, output_name,
        self._make_tool_progress_callback('subtitle')
    )

def subtitle_merge_api(self, file_a: str, file_b: str,
                       output_dir: str = "", output_name: str = "",
                       layout: str = "top_bottom") -> Dict:
    if not output_dir:
        output_dir = self.settings.get("output_dir") or os.path.dirname(file_a)
    return self._tool_svc.subtitle_merge_api(
        file_a, file_b, output_dir, output_name, layout,
        self._make_tool_progress_callback('subtitle')
    )

def subtitle_convert_api(self, input_file: str, target_format: str,
                         output_dir: str = "", output_name: str = "") -> Dict:
    if not output_dir:
        output_dir = self.settings.get("output_dir") or os.path.dirname(input_file)
    return self._tool_svc.subtitle_convert_api(
        input_file, target_format, output_dir, output_name,
        self._make_tool_progress_callback('subtitle')
    )

def subtitle_split_api(self, input_file: str,
                       output_dir: str = "", output_name: str = "",
                       pattern: str = "") -> Dict:
    if not output_dir:
        output_dir = self.settings.get("output_dir") or os.path.dirname(input_file)
    return self._tool_svc.subtitle_split_api(
        input_file, output_dir, output_name, pattern or None,
        self._make_tool_progress_callback('subtitle')
    )

def subtitle_extract_api(self, input_file: str,
                         output_dir: str = "", output_name: str = "",
                         stream_index: int = 0, output_format: str = "srt") -> Dict:
    if not output_dir:
        output_dir = self.settings.get("output_dir") or os.path.dirname(input_file)
    return self._tool_svc.subtitle_extract_api(
        input_file, output_dir, output_name, stream_index, output_format,
        self._make_tool_progress_callback('subtitle')
    )
```

- [ ] **Step 3: 提交**

```bash
git add src/fisheep_video_merger/utils/bridge.py
git commit -m "feat(subtitle): 添加字幕桥接方法和 settings 注册"
```

---

### Task 5: 创建 JS 工具模块 `subtitle.js`

**Files:**
- Create: `src/fisheep_video_merger/ui/web/js/tools/subtitle.js`

- [ ] **Step 1: 创建文件**

```javascript
export const Subtitle = {
    start: () => {
        const tool = 'subtitle';
        if (!window.toolFiles || !window.toolFiles[tool] || window.toolFiles[tool].length === 0) {
            window.showToast('当前队列中没有文件', 'warning');
            return;
        }

        const operation = Alpine.store('settings').toolSettings.subtitle.operation;
        const outputDir = document.getElementById('subtitle-output-dir')?.value || '';
        const outputName = Alpine.store('settings').toolSettings.subtitle.outputName?.trim() || '';

        const checkedCount = document.querySelectorAll(`#${tool}-tbody .tool-row-cb:checked`).length;
        const selCount = checkedCount || window.toolFiles[tool].length;
        const nameForBatch = selCount === 1 ? outputName : '';

        window.runToolTask(tool, (file) => {
            switch (operation) {
                case 'adjust': {
                    const offsetMs = parseFloat(document.getElementById('subtitle-offset')?.value || '0') * 1000;
                    return window.pywebview.api.subtitle_adjust_api(file.filepath, offsetMs, outputDir, nameForBatch);
                }
                case 'convert': {
                    const format = document.getElementById('subtitle-format')?.value || 'srt';
                    return window.pywebview.api.subtitle_convert_api(file.filepath, format, outputDir, nameForBatch);
                }
                case 'extract': {
                    const streamIndex = parseInt(document.getElementById('subtitle-stream')?.value || '0');
                    const format = document.getElementById('subtitle-extract-format')?.value || 'srt';
                    return window.pywebview.api.subtitle_extract_api(file.filepath, outputDir, nameForBatch, streamIndex, format);
                }
                case 'split': {
                    const pattern = document.getElementById('subtitle-split-pattern')?.value || '';
                    return window.pywebview.api.subtitle_split_api(file.filepath, outputDir, nameForBatch, pattern);
                }
                default:
                    return Promise.resolve({ status: 'error', message: '未知操作类型' });
            }
        });
    },

    startMerge: () => {
        const tool = 'subtitle';
        const fileA = document.getElementById('subtitle-merge-file-a')?.value || '';
        const fileB = document.getElementById('subtitle-merge-file-b')?.value || '';
        if (!fileA || !fileB) {
            window.showToast('请选择两个字幕文件', 'warning');
            return;
        }
        const layout = document.getElementById('subtitle-merge-layout')?.value || 'top_bottom';
        const outputDir = document.getElementById('subtitle-output-dir')?.value || '';
        const outputName = Alpine.store('settings').toolSettings.subtitle.outputName?.trim() || '';

        window.pywebview.api.subtitle_merge_api(fileA, fileB, outputDir, outputName, layout).then(result => {
            if (result.status === 'success') {
                window.showToast('字幕合并完成', 'success');
            } else {
                window.showToast(result.message || '合并失败', 'error');
            }
        });
    }
};
```

- [ ] **Step 2: 提交**

```bash
git add src/fisheep_video_merger/ui/web/js/tools/subtitle.js
git commit -m "feat(subtitle): 创建 JS 工具模块"
```

---

### Task 6: 接入 main.js

**Files:**
- Modify: `src/fisheep_video_merger/ui/web/js/main.js`

- [ ] **Step 1: 添加 import**

在 import 区域（`import { Trimmer } from './tools/trimmer.js';` 之后）添加：

```javascript
import { Subtitle } from './tools/subtitle.js';
```

- [ ] **Step 2: 添加路由**

在 `window.startToolTask` 函数中，在 `else if (tool === 'trim')` 之后添加：

```javascript
else if (tool === 'subtitle') Subtitle.start();
```

- [ ] **Step 3: 添加到 Alpine store**

在 `main.js` 中 Alpine store 初始化的 `toolOutputDirs` 和 `toolSettings` 对象里添加 subtitle 条目：

在 `toolOutputDirs` 中添加：
```javascript
subtitle: '',
```

在 `toolSettings` 中添加：
```javascript
subtitle: { operation: 'adjust', offsetMs: 0, layout: 'top_bottom', outputName: '' },
```

- [ ] **Step 4: 提交**

```bash
git add src/fisheep_video_merger/ui/web/js/main.js
git commit -m "feat(subtitle): 接入 main.js 导入、路由和 Alpine store"
```

---

### Task 7: 接入 settings.js

**Files:**
- Modify: `src/fisheep_video_merger/ui/web/js/settings.js`

- [ ] **Step 1: 添加到 toolFiles**

修改 `window.toolFiles` 声明：

```javascript
window.toolFiles = { convert: [], extract: [], compress: [], trim: [], subtitle: [] };
```

- [ ] **Step 2: 添加到 initToolDropZones**

在 `initToolDropZones` 函数的数组中添加 `'subtitle'`：

```javascript
['convert', 'extract', 'compress', 'trim', 'subtitle'].forEach(tool => {
```

- [ ] **Step 3: 添加 start 按钮事件**

在 `initToolStartButtons` 函数末尾追加：

```javascript
// 字幕工具
const subtitleBtn = document.getElementById('subtitle-start-btn');
if (subtitleBtn) {
    subtitleBtn.addEventListener('click', () => {
        Subtitle.start();
    });
}

// 字幕合并（独立按钮）
const subtitleMergeBtn = document.getElementById('subtitle-merge-btn');
if (subtitleMergeBtn) {
    subtitleMergeBtn.addEventListener('click', () => {
        Subtitle.startMerge();
    });
}
```

注意：需要在文件顶部添加 import：

```javascript
import { Subtitle } from './tools/subtitle.js';
```

- [ ] **Step 4: 提交**

```bash
git add src/fisheep_video_merger/ui/web/js/settings.js
git commit -m "feat(subtitle): 接入 settings.js 事件绑定"
```

---

### Task 8: 接入 bridge.js 设置同步

**Files:**
- Modify: `src/fisheep_video_merger/ui/web/js/bridge.js`

- [ ] **Step 1: 添加工具输出目录同步**

在 `syncSettingsFromPython` 函数的 `tool_output_dirs` 同步数组中添加 `'subtitle'`：

```javascript
['convert', 'extract', 'compress', 'trim', 'subtitle'].forEach(tool => {
```

- [ ] **Step 2: 添加工具设置同步**

在 `tool_settings` 同步的 `if (ts.trim)` 块之后添加：

```javascript
if (ts.subtitle) {
    const op = document.getElementById('subtitle-operation');
    if (op) op.value = ts.subtitle.operation || 'adjust';
    const offset = document.getElementById('subtitle-offset');
    if (offset) offset.value = (ts.subtitle.offset_ms || 0) / 1000;
}
```

- [ ] **Step 3: 提交**

```bash
git add src/fisheep_video_merger/ui/web/js/bridge.js
git commit -m "feat(subtitle): 接入 bridge.js 设置同步"
```

---

### Task 9: 添加 HTML 工具面板 `index.html`

**Files:**
- Modify: `src/fisheep_video_merger/ui/web/index.html`

- [ ] **Step 1: 添加侧栏导航按钮**

在 `<nav class="nav-links">` 中，`<button data-tool="trim">` 之后添加：

```html
<button class="nav-btn" data-tool="subtitle"
        :class="{ 'active': $store.app.currentTool === 'subtitle' }"
        @click="$store.app.currentTool = 'subtitle'; window.location.hash = 'subtitle'">
    <span class="nav-icon">📝</span>
    <span class="nav-text">字幕工具</span>
</button>
```

- [ ] **Step 2: 添加工具面板**

在 `tool-trim` 面板之后，`</main>` 之前添加：

```html
<!-- ========== 工具面板：字幕工具 ========== -->
<div class="tool-panel" id="tool-subtitle" :class="{ 'active': $store.app.currentTool === 'subtitle' }">
    <header class="tool-header">
        <div>
            <h2>📝 字幕工具</h2>
            <p class="subtitle">字幕调轴、合并、转换、拆分、提取、批量处理</p>
        </div>
        <div class="header-actions">
            <button class="btn btn-secondary" onclick="selectFilesForTool('subtitle')">📄 添加文件</button>
        </div>
    </header>

    <!-- 子功能 Tab 栏 -->
    <div class="subtab-bar" x-data="{ activeTab: 'adjust' }">
        <button class="btn" :class="{ 'active': activeTab === 'adjust' }"
                @click="activeTab = 'adjust'; $store.settings.toolSettings.subtitle.operation = 'adjust'">🔄 调轴</button>
        <button class="btn" :class="{ 'active': activeTab === 'merge' }"
                @click="activeTab = 'merge'; $store.settings.toolSettings.subtitle.operation = 'merge'">🔗 合并</button>
        <button class="btn" :class="{ 'active': activeTab === 'convert' }"
                @click="activeTab = 'convert'; $store.settings.toolSettings.subtitle.operation = 'convert'">🔄 转换</button>
        <button class="btn" :class="{ 'active': activeTab === 'split' }"
                @click="activeTab = 'split'; $store.settings.toolSettings.subtitle.operation = 'split'">✂️ 拆分</button>
        <button class="btn" :class="{ 'active': activeTab === 'extract' }"
                @click="activeTab = 'extract'; $store.settings.toolSettings.subtitle.operation = 'extract'">📤 提取</button>
        <button class="btn" :class="{ 'active': activeTab === 'batch' }"
                @click="activeTab = 'batch'; $store.settings.toolSettings.subtitle.operation = 'batch'">📦 批量</button>
    </div>

    <!-- 调轴参数 -->
    <div class="tool-options" x-show="activeTab === 'adjust'" x-data>
        <div class="tool-option-group">
            <label>偏移量（秒）</label>
            <input type="number" id="subtitle-offset" step="0.1" value="0" placeholder="正数延后，负数提前">
        </div>
        <div class="tool-option-group" style="flex: 1;">
            <label>输出目录</label>
            <div style="display: flex; gap: 8px;">
                <input type="text" id="subtitle-output-dir" placeholder="默认与源文件同目录" readonly style="flex: 1;">
                <button class="mini-action-btn" onclick="selectToolOutputDir('subtitle')">📂</button>
            </div>
        </div>
        <div class="tool-option-group" style="flex: 1;">
            <label>输出文件名 <span style="color: var(--text-muted); font-weight: normal;">（留空则自动命名）</span></label>
            <input type="text" id="subtitle-output-name" x-model="$store.settings.toolSettings.subtitle.outputName" placeholder="例如: 调轴后的字幕">
        </div>
    </div>

    <!-- 合并参数 -->
    <div class="tool-options" x-show="activeTab === 'merge'" x-data>
        <div class="tool-option-group" style="flex: 1;">
            <label>字幕文件 A</label>
            <div style="display: flex; gap: 8px;">
                <input type="text" id="subtitle-merge-file-a" placeholder="选择第一个字幕文件" readonly style="flex: 1;">
                <button class="mini-action-btn" onclick="selectSubtitleFile('a')">📂</button>
            </div>
        </div>
        <div style="text-align: center; padding: 4px 0; color: var(--text-muted);">↕ 合并为双语字幕</div>
        <div class="tool-option-group" style="flex: 1;">
            <label>字幕文件 B</label>
            <div style="display: flex; gap: 8px;">
                <input type="text" id="subtitle-merge-file-b" placeholder="选择第二个字幕文件" readonly style="flex: 1;">
                <button class="mini-action-btn" onclick="selectSubtitleFile('b')">📂</button>
            </div>
        </div>
        <div class="tool-option-group">
            <label>布局</label>
            <select id="subtitle-merge-layout">
                <option value="top_bottom">上下双语</option>
                <option value="left_right">左右列</option>
            </select>
        </div>
        <div class="tool-option-group" style="flex: 1;">
            <label>输出目录</label>
            <div style="display: flex; gap: 8px;">
                <input type="text" id="subtitle-output-dir-merge" placeholder="默认与源文件同目录" readonly style="flex: 1;">
                <button class="mini-action-btn" onclick="selectToolOutputDir('subtitle')">📂</button>
            </div>
        </div>
    </div>

    <!-- 转换参数 -->
    <div class="tool-options" x-show="activeTab === 'convert'" x-data>
        <div class="tool-option-group">
            <label>目标格式</label>
            <select id="subtitle-format">
                <option value="srt">SRT</option>
                <option value="ass">ASS</option>
                <option value="vtt">VTT</option>
                <option value="ssa">SSA</option>
            </select>
        </div>
        <div class="tool-option-group" style="flex: 1;">
            <label>输出目录</label>
            <div style="display: flex; gap: 8px;">
                <input type="text" id="subtitle-output-dir-convert" placeholder="默认与源文件同目录" readonly style="flex: 1;">
                <button class="mini-action-btn" onclick="selectToolOutputDir('subtitle')">📂</button>
            </div>
        </div>
    </div>

    <!-- 拆分参数 -->
    <div class="tool-options" x-show="activeTab === 'split'" x-data>
        <div class="tool-option-group">
            <label>拆分规则</label>
            <select id="subtitle-split-mode">
                <option value="evenodd">奇偶行拆分</option>
                <option value="regex">正则表达式</option>
            </select>
        </div>
        <div class="tool-option-group" style="flex: 1;">
            <label>正则表达式（选择正则时生效）</label>
            <input type="text" id="subtitle-split-pattern" placeholder="例如: ^[A-Za-z] 匹配英文行">
        </div>
        <div class="tool-option-group" style="flex: 1;">
            <label>输出目录</label>
            <div style="display: flex; gap: 8px;">
                <input type="text" id="subtitle-output-dir-split" placeholder="默认与源文件同目录" readonly style="flex: 1;">
                <button class="mini-action-btn" onclick="selectToolOutputDir('subtitle')">📂</button>
            </div>
        </div>
    </div>

    <!-- 提取参数 -->
    <div class="tool-options" x-show="activeTab === 'extract'" x-data>
        <div class="tool-option-group">
            <label>字幕流</label>
            <select id="subtitle-stream">
                <option value="0">第一个字幕流</option>
            </select>
        </div>
        <div class="tool-option-group">
            <label>输出格式</label>
            <select id="subtitle-extract-format">
                <option value="srt">SRT</option>
                <option value="ass">ASS</option>
                <option value="vtt">VTT</option>
            </select>
        </div>
        <div class="tool-option-group" style="flex: 1;">
            <label>输出目录</label>
            <div style="display: flex; gap: 8px;">
                <input type="text" id="subtitle-output-dir-extract" placeholder="默认与源文件同目录" readonly style="flex: 1;">
                <button class="mini-action-btn" onclick="selectToolOutputDir('subtitle')">📂</button>
            </div>
        </div>
    </div>

    <!-- 批量参数 -->
    <div class="tool-options" x-show="activeTab === 'batch'" x-data>
        <div class="tool-option-group">
            <label>批量操作</label>
            <select id="subtitle-batch-operation">
                <option value="adjust">整体调轴</option>
                <option value="convert">格式转换</option>
                <option value="split">拆分双语</option>
            </select>
        </div>
        <div class="tool-option-group" style="flex: 1;">
            <label>输出目录</label>
            <div style="display: flex; gap: 8px;">
                <input type="text" id="subtitle-output-dir-batch" placeholder="默认与源文件同目录" readonly style="flex: 1;">
                <button class="mini-action-btn" onclick="selectToolOutputDir('subtitle')">📂</button>
            </div>
        </div>
    </div>

    <div x-data="{ localTool: 'subtitle', actionName: '处理' }">
        <task-list></task-list>

    <action-bar></action-bar>
    </div>
</div>
```

- [ ] **Step 3: 提交**

```bash
git add src/fisheep_video_merger/ui/web/index.html
git commit -m "feat(subtitle): 添加字幕工具 HTML 面板和侧栏按钮"
```

---

### Task 10: 更新任务列表组件 `task_list.html`

**Files:**
- Modify: `src/fisheep_video_merger/ui/web/components/task_list.html`

- [ ] **Step 1: 添加字幕列定义**

在 `<task-list>` 组件的模板中，找到其他工具的 `<template x-if="localTool === '...'}">` 块，在之后添加字幕工具的列定义：

```html
<template x-if="localTool === 'subtitle'">
    <tr>
        <td><input type="checkbox" class="tool-row-cb" :data-index="index"></td>
        <td>
            <span x-text="file.name" style="font-weight: 600;"></span>
        </td>
        <td>
            <span x-text="file.format || '-'" style="font-size: 11px; color: var(--text-muted);"></span>
        </td>
        <td>
            <span x-text="file.size || '-'" style="font-size: 11px; color: var(--text-muted);"></span>
        </td>
        <td>
            <span x-show="file.status === 'pending'" style="color: var(--text-muted);">⏳ 等待</span>
            <div x-show="file.status === 'processing'" class="table-progress-bar">
                <div class="table-progress-chunk" :style="'width:' + (file.percent || 0) + '%'"></div>
                <span class="table-progress-text" x-text="(file.percent || 0) + '%'"></span>
            </div>
            <span x-show="file.status === 'completed'" style="color: var(--primary-color);">✅ 完成</span>
            <span x-show="file.status === 'failed'" style="color: #EF4444;" :title="file.error || ''">❌ 失败</span>
        </td>
        <td style="white-space: nowrap;">
            <button class="mini-action-btn" @click.stop="openToolFile(file)" title="播放" style="color: #10B981;">▶</button>
            <button class="mini-action-btn" @click.stop="openToolFileFolder(file)" title="打开目录" style="color: #3B82F6;">📂</button>
            <button class="mini-action-btn" @click.stop="removeToolFile(localTool, index)" title="移除" style="color: #EF4444;">✕</button>
        </td>
    </tr>
</template>
```

- [ ] **Step 2: 提交**

```bash
git add src/fisheep_video_merger/ui/web/components/task_list.html
git commit -m "feat(subtitle): 添加字幕工具任务列表列定义"
```

---

### Task 11: 最终验证和提交

- [ ] **Step 1: 运行应用验证**

Run: `PYTHONPATH=src python -m fisheep_video_merger.main_web`
Expected: 应用正常启动，侧栏显示「字幕工具」按钮，点击后显示工具面板

- [ ] **Step 2: 测试整体调轴**

1. 准备一个 .srt 字幕文件
2. 拖入字幕工具面板
3. 选择「调轴」子功能
4. 输入偏移量 +2.5 秒
5. 点击开始
6. 验证输出文件时间轴偏移正确

- [ ] **Step 3: 测试格式转换**

1. 准备一个 .srt 文件
2. 切换到「转换」子功能
3. 选择目标格式 ass
4. 点击开始
5. 验证输出为 .ass 文件且内容正确

- [ ] **Step 4: 测试字幕合并**

1. 准备两个 .srt 文件
2. 切换到「合并」子功能
3. 分别选择文件 A 和文件 B
4. 点击合并
5. 验证输出为双语字幕

- [ ] **Step 5: 提交所有变更**

```bash
git add -A
git commit -m "feat: 完成字幕工具全部功能（调轴/合并/转换/拆分/提取/批量）"
```
