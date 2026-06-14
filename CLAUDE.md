# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

Fisheep 视频工具箱 — Windows 桌面应用，支持合并分离式音视频文件、格式转换、音频提取、视频压缩、视频裁剪等多功能。支持 B站（m4s）、YouTube（webm/mp4）、通用格式（mp4/mkv/ts + aac/mp3/flac）等多平台缓存。当前版本 v0.9.0。

## 常用命令

```bash
# 安装依赖
pip install -r requirements.txt

# 运行（WebView 模式，当前主版本）
PYTHONPATH=src python -m fisheep_video_merger.main_web

# 打包 EXE（PyInstaller 单文件，约 21MB）
python build.py
```

运行前需确保 FFmpeg/ffprobe 已安装并在 PATH 中。无测试套件、无 linter、无 CI。

## 架构

**技术栈**：Python 3.12 + pywebview（Edge WebView2）+ HTML/CSS/JS + Alpine.js。PyInstaller 打包为单文件 EXE。

**WebView 前端**：纯前端，无构建工具，通过 pywebview 的 `file://` 协议直接加载。前端文件在 `src/fisheep_video_merger/ui/web/`，JS 按职责拆分为 `main.js`（入口）、`bridge.js`（Python 调用封装）、`store.js`（Alpine store）、`merger.js`、`settings.js`、`ui.js`，工具页独立在 `js/tools/` 下（converter/extractor/compressor/trimmer）。HTML 组件在 `components/` 下（action_bar / batch_panel / file_drop_area / task_list）。

**Python-JS 桥接**：`utils/bridge.py` 中的 `UIBridge` 类是薄门面，通过 pywebview 的 `js_api` 暴露方法给 JS。实际业务委托给 `utils/services/` 下的独立服务：
- `state_persistence.py` — 工作区状态持久化
- `task_manager.py` — 任务队列管理
- `merge_controller.py` — 合并流程控制
- `tool_service.py` — 工具页操作（转换/提取/压缩/裁剪）
- `dialog_service.py` — 对话框服务

`UIBridge` 还直接持有 `BatchProcessor`（来自 `core.batch`），暴露 `batch_import` / `batch_preview` / `batch_merge` 三个批处理 API。

JS 调 Python 用 `window.pywebview.api.methodName()`，Python 推送更新到 JS 用 `window.evaluate_js()`。

**核心业务逻辑**（`core/` 目录，无 UI 依赖）：
- `scanner.py` — 多线程目录扫描 + ffprobe 分析
- `matcher.py` — 策略模式匹配管线（DirectoryMatch / CleanStemMatch / EpisodeInterlock 三种策略按序执行）
- `merger.py` — FFmpeg 合并执行
- `ffmpeg_runner.py` — 统一 FFmpeg 执行器，所有操作（merge/convert/extract/compress/trim）经此分发
- `converter.py` / `extractor.py` / `compressor.py` / `trimmer.py` — 各工具页业务逻辑
- `models.py` — 数据模型（MergeTask / MatchResult）
- `episode.py` — 集数提取
- `naming.py` — 命名模板系统
- `bilibili.py` — B站元数据读取
- `batch.py` — 批处理引擎（Batch/BatchProcessor，多文件夹批量扫描+合并）

**状态持久化**：工作区状态保存在 `%LOCALAPPDATA%/fisheep-video-merger/workspace_state.json`。

**并发模型**：扫描用 `ThreadPoolExecutor`（4 workers），合并用可配置并发（1-8）。进度通过 `evaluate_js` 回传 UI。

## 关键约束

- **打包路径嗅探（sys.frozen）**：修改路径解析/配置/日志的代码必须处理 `sys.frozen`，持久化资源默认通过 `sys.executable` 定位，防止 EXE 运行时 `_MEIPASS` 临时目录数据丢失。
- **线程安全 UI 更新**：后台线程不得直接修改 UI 控件，必须通过 `evaluate_js` 回传主线程。
- **代码注释**：代码内所有注释、Docstring、技术文档必须使用中文（除非破坏语法或标准库约束）。
- **语言**：所有解释、分析、架构说明必须使用清晰精确的中文。

## Agent skills

### Issue tracker

本地 markdown，issue 存放在 `.scratch/` 目录。See `docs/agents/issue-tracker.md`.

### Triage labels

使用默认标签：needs-triage / needs-info / ready-for-agent / ready-for-human / wontfix。See `docs/agents/triage-labels.md`.

### Domain docs

Single-context 布局，`CONTEXT.md` + `docs/adr/` 在项目根目录。See `docs/agents/domain.md`.
