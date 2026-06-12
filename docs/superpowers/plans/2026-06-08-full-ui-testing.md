# 全面 UI 测试计划

> **Goal:** 对 Fisheep 视频工具箱的 6 个工具标签页进行全面的 Playwright 自动化测试，覆盖 UI 元素验证、参数面板切换、核心功能调用。

**Architecture:** 使用 Playwright Python 脚本，通过 pywebview 的内置 HTTP 服务器连接应用前端，验证所有 UI 交互。

**Tech Stack:** Playwright Python, Chromium headless

---

## 测试策略

### 分层测试

| 层级 | 内容 | 方法 |
|------|------|------|
| L1: DOM 验证 | 所有元素存在、ID 匹配 | Playwright 查询选择器 |
| L2: 交互验证 | Tab 切换、参数面板显示/隐藏 | Playwright 点击 + 可见性检查 |
| L3: 功能验证 | 核心函数正确性 | Python 单元测试（已通过） |
| L4: 集成验证 | 前端→桥接→服务→核心 全链路 | 需要 pywebview 运行时 |

### 已发现的 Bug（需修复后重新测试）

| # | Bug | 位置 | 说明 |
|---|-----|------|------|
| 1 | 裁剪模式不匹配 | HTML `#trim-mode` vs `tool_service.py` | HTML 值 `copy`/`recode`，但服务检查 `mode == "accurate"`，`recode` 不会触发精确模式 |
| 2 | 字幕合并布局不匹配 | HTML `#subtitle-merge-layout` vs `core/subtitle.py` | HTML 值 `vertical`/`horizontal`/`interleave`，但核心只处理 `top_bottom` 和 `interleave` |

---

## 测试用例

### Tool 1: 音视频合并 (merge)

| # | 用例 | 验证点 |
|---|------|--------|
| 1.1 | 侧栏按钮存在 | `button[data-tool="merge"]` 存在，文字包含"合并" |
| 1.2 | 面板切换 | 点击后面板 `#tool-merge` 可见 |
| 1.3 | 子标签存在 | 合并队列/待整理/已完整/批量合并 4 个子标签 |
| 1.4 | 导入按钮存在 | `#add-folder-btn`、`#add-files-btn`、`#clear-btn` 存在 |
| 1.5 | 配置面板元素 | `#global-output-dir`、`#merge-format`、`#merge-concurrency` 存在 |
| 1.6 | 格式选项 | `#merge-format` 有 `mp4`、`mkv` 选项 |

### Tool 2: 格式转换 (convert)

| # | 用例 | 验证点 |
|---|------|--------|
| 2.1 | 侧栏按钮存在 | `button[data-tool="convert"]` 存在 |
| 2.2 | 面板切换 | `#tool-convert` 可见 |
| 2.3 | 目标格式选项 | `#convert-format` 有 mp4/mkv/webm/avi |
| 2.4 | 转换模式选项 | `#convert-mode` 有 copy/recode |
| 2.5 | 输出目录输入框 | `#convert-output-dir` 存在 |
| 2.6 | 输出文件名输入框 | `#convert-output-name` 存在 |

### Tool 3: 提取音频 (extract)

| # | 用例 | 验证点 |
|---|------|--------|
| 3.1 | 侧栏按钮存在 | `button[data-tool="extract"]` 存在 |
| 3.2 | 面板切换 | `#tool-extract` 可见 |
| 3.3 | 音频格式选项 | `#extract-format` 有 mp3/aac/flac/wav |
| 3.4 | 码率选项 | `#extract-bitrate` 有 64k/128k/192k/256k/320k |
| 3.5 | 码率模式 | `#extract-bitrate-mode` 有 cbr/vbr |
| 3.6 | 声道选项 | `#extract-channels` 有 original/stereo/mono |
| 3.7 | 采样率选项 | `#extract-sample-rate` 有 original/8000/11025/22050/44100/48000 |
| 3.8 | 音量滑块 | `#extract-volume` 存在 |
| 3.9 | 预设按钮 | high/medium/low 预设按钮存在 |

### Tool 4: 视频压缩 (compress)

| # | 用例 | 验证点 |
|---|------|--------|
| 4.1 | 侧栏按钮存在 | `button[data-tool="compress"]` 存在 |
| 4.2 | 面板切换 | `#tool-compress` 可见 |
| 4.3 | 压缩预设 | `#compress-preset` 有 fast/balanced/quality |
| 4.4 | 分辨率选项 | `#compress-resolution` 有 original/1080p/720p/480p |
| 4.5 | 输出目录 | `#compress-output-dir` 存在 |

### Tool 5: 视频裁剪 (trim)

| # | 用例 | 验证点 |
|---|------|--------|
| 5.1 | 侧栏按钮存在 | `button[data-tool="trim"]` 存在 |
| 5.2 | 面板切换 | `#tool-trim` 可见 |
| 5.3 | 开始时间输入 | `#trim-start` 存在 |
| 5.4 | 结束时间输入 | `#trim-end` 存在 |
| 5.5 | 裁剪模式 | `#trim-mode` 存在 |
| 5.6 | 时间线组件 | `#trim-timeline` 存在（如果实现了） |

### Tool 6: 字幕工具 (subtitle)

| # | 用例 | 验证点 |
|---|------|--------|
| 6.1 | 侧栏按钮存在 | `button[data-tool="subtitle"]` 存在 |
| 6.2 | 面板切换 | `#tool-subtitle` 可见 |
| 6.3 | 6 个子 Tab | 调轴/合并/转换/拆分/提取/批量 全部存在 |
| 6.4 | 调轴面板 | `#subtitle-adjust-offset` 存在 |
| 6.5 | 合并面板 | `#subtitle-merge-file-a`、`#subtitle-merge-file-b`、`#subtitle-merge-layout` 存在 |
| 6.6 | 转换面板 | `#subtitle-convert-format` 有 srt/ass/ssa/vtt/sub |
| 6.7 | 拆分面板 | `#subtitle-split-rule`、`#subtitle-split-regex` 存在 |
| 6.8 | 提取面板 | `#subtitle-extract-stream`、`#subtitle-extract-format` 存在 |
| 6.9 | 批量面板 | `#subtitle-batch-operation` 存在 |
| 6.10 | Tab 切换验证 | 点击每个 Tab 后对应参数面板可见 |

---

## 执行顺序

1. **修复已发现的 Bug**（裁剪模式 + 字幕合并布局）
2. **启动应用**（pywebview HTTP server）
3. **运行 L1 DOM 验证测试**（所有元素存在性）
4. **运行 L2 交互验证测试**（Tab 切换、面板可见性）
5. **截图存档**
6. **提交测试结果**
