# 🐑 Fisheep 视频工具箱

<p align="center">
  <img src="https://img.shields.io/badge/Version-v0.5.5-brightgreen?style=for-the-badge" alt="Version">
  <img src="https://img.shields.io/badge/Platform-Windows_10%2B-blue?style=for-the-badge&logo=windows" alt="Platform">
  <img src="https://img.shields.io/badge/License-MIT-orange?style=for-the-badge" alt="License">
</p>

Fisheep 视频工具箱 — Windows 桌面应用，支持合并分离式音视频文件、格式转换、音频提取、视频压缩、视频裁剪等多功能。

支持 B站（m4s）、YouTube（webm/mp4）、通用格式（mp4/mkv/ts + aac/mp3/flac）等多平台缓存。

---

## 功能特性

### 合并工具
- 🔍 递归深度扫描，自动识别音视频流类型
- 🤖 三种配对策略（目录级/骨架匹配/集数互锁）
- ⚡ 多线程并发合并，支持 1-8 并发
- 📊 实时进度条 + ETA 预估
- ✏️ 双击输出名内联编辑
- 📝 命名模板系统（`{series}_{ep}` 等变量）
- 💾 工作区状态持久化

### 视频工具
- 🔄 格式转换（流复制/重编码，支持硬件加速）
- 🎵 音频提取（MP3/AAC/FLAC/WAV，支持声道/采样率/音量调节）
- 📦 视频压缩（快速/均衡/高质量三档）
- ✂️ 视频裁剪（无损/重编码两种模式）

### 通用功能
- 🖼️ 视频预览（截图 + 元数据）
- 📂 多平台格式支持（B站/YouTube/通用）
- 🎯 硬件加速检测（NVENC/QSV/AMF）
- 📋 导出/导入配对配置
- 🖱️ 拖拽排序队列

---

## 快速开始

### 方案 A：下载 EXE（推荐）
1. 前往 [Releases](https://github.com/chycycc/fisheep-video-merger/releases) 页面
2. 下载最新版 `FisheepVideoMerger.exe`（约 21MB）
3. 双击运行（需系统已安装 FFmpeg 并加入 PATH）

### 方案 B：源码运行
```bash
git clone https://github.com/chycycc/fisheep-video-merger.git
cd fisheep-video-merger
pip install -r requirements.txt
PYTHONPATH=src python -m fisheep_video_merger.main_web
```

---

## 技术栈

- **后端**：Python 3.12 + pywebview（Edge WebView2）
- **前端**：HTML/CSS/JS + Alpine.js
- **处理**：FFmpeg/ffprobe
- **打包**：PyInstaller → 单文件 EXE（~21MB）

---

## 项目结构

```
src/fisheep_video_merger/
├── core/                    # 业务逻辑（无 UI 依赖）
│   ├── models.py            # 数据模型（MergeTask/MatchResult）
│   ├── matcher.py           # 配对策略管道
│   ├── scanner.py           # 多线程文件扫描
│   ├── merger.py            # 音视频合并
│   ├── converter.py         # 格式转换
│   ├── extractor.py         # 音频提取
│   ├── compressor.py        # 视频压缩
│   ├── trimmer.py           # 视频裁剪
│   ├── ffmpeg_runner.py     # FFmpeg 执行器 + 硬件加速检测
│   ├── episode.py           # 集数提取
│   ├── naming.py            # 命名模板
│   └── bilibili.py          # B站元数据读取
├── ui/web/                  # WebView 前端
│   ├── index.html           # 主页面
│   ├── app.js               # 前端逻辑
│   └── style.css            # 样式
├── utils/                   # 工具模块
│   ├── bridge.py            # Python-JS 桥接门面
│   ├── services/            # 服务层
│   │   ├── state_persistence.py
│   │   ├── task_manager.py
│   │   ├── merge_controller.py
│   │   ├── tool_service.py
│   │   └── dialog_service.py
│   ├── ffprobe.py           # 流分析
│   └── logger.py            # 日志
└── main_web.py              # WebView 入口
```

---

## 开发命令

```bash
# 安装依赖
pip install -r requirements.txt

# 运行（WebView 模式）
PYTHONPATH=src python -m fisheep_video_merger.main_web

# 打包 EXE
python build.py
```

---

MIT License © 2026 Fisheep Team.
