# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

Fisheep Video Merger — Windows 桌面应用，用于合并 Bilibili 缓存的 m4s 分离式音视频文件。当前版本 v0.5.3。

## 常用命令

```bash
# 安装依赖
pip install -r requirements.txt

# 运行（WebView 模式，当前主版本）
PYTHONPATH=src python -m fisheep_video_merger.main_web

# 运行（PySide6 模式，遗留版本）
PYTHONPATH=src python src/fisheep_video_merger/main.py

# 打包 EXE
python build.py
```

运行前需确保 FFmpeg/ffprobe 已安装并在 PATH 中。无测试套件、无 linter、无 CI。

## 架构

**双 UI 模式**：PySide6（遗留，`main.py`）和 WebView（当前，`main_web.py`）。活跃开发自 v0.4.0 起已转向 WebView。

**WebView 前端**：纯 HTML/CSS/JS + Alpine.js，无构建工具，通过 pywebview 的 `file://` 协议直接加载。前端文件在 `src/fisheep_video_merger/ui/web/`。

**Python-JS 桥接**：`utils/bridge.py` 中的 `UIBridge` 类通过 pywebview 的 `js_api` 暴露方法给 JS。JS 调用 Python 用 `window.pywebview.api.methodName()`，Python 推送更新到 JS 用 `window.evaluate_js()`。

**核心业务逻辑**（`core/` 目录，无 UI 依赖）：
- `scanner.py` — 多线程目录扫描 + ffprobe 分析
- `matcher.py` — 策略模式匹配管线（DirectoryMatch / CleanStemMatch / EpisodeInterlock 三种策略按序执行）
- `merger.py` — FFmpeg 合并执行
- `ffmpeg_runner.py` — 统一 FFmpeg 执行器，所有操作（merge/convert/extract/compress/trim）经此分发

**状态持久化**：工作区状态保存在 `%LOCALAPPDATA%/fisheep-video-merger/workspace_state.json`。

**并发模型**：扫描用 `ThreadPoolExecutor`（4 workers），合并用可配置并发（1-8）。进度通过 `evaluate_js` 回传 UI。

## 关键约束

- **打包路径嗅探（sys.frozen）**：修改路径解析/配置/日志的代码必须处理 `sys.frozen`，持久化资源默认通过 `sys.executable` 定位，防止 EXE 运行时 `_MEIPASS` 临时目录数据丢失。
- **Qt 事件循环非阻塞**：与 FFmpeg/流分析交互时禁止在主线程引入长同步代码，保留 150ms 时间窗口 + 1% 变化量双重节流。
- **线程安全 UI 更新**：`MergeWorker` 线程不得直接修改 UI 控件，必须通过 Qt Signals/Slots 分发到主线程。
- **代码注释**：代码内所有注释、Docstring、技术文档必须使用中文（除非破坏语法或标准库约束）。
- **语言**：所有解释、分析、架构说明必须使用清晰精确的中文。
