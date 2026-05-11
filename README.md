# B站 m4s 视频合并工具

一个 Windows 桌面工具，用于合并 B站（Bilibili）下载的 m4s 格式视频和音频文件。

## 功能特点

- 🔍 **自动扫描** — 递归扫描文件夹，自动识别 m4s 文件的流类型（视频/音频/混合）
- 🤖 **智能配对** — 基于文件夹结构自动配对视频和音频文件，支持单对和多对场景
- 🏷️ **智能集数识别** — 自动从文件名提取集数信息（如 `第3集`、`EP03`、`#05`），输出文件自动添加 `_03` 后缀
- ✅ **选择性合并** — 通过复选框勾选需要合并的任务，支持批量操作
- 📝 **批量重命名** — 支持前缀 + 起始序号批量重命名输出文件
- 🎬 **多格式输出** — 支持 mp4 / mkv / mov / flv 格式
- 🗑️ **安全删除** — 合并完成后可选择将源文件移至回收站
- 🖱️ **拖拽支持** — 支持拖拽文件夹到窗口添加
- 📊 **进度显示** — 实时显示合并进度和任务状态

## 系统要求

- Windows 10+
- Python 3.9+
- [FFmpeg](https://ffmpeg.org/)（需添加到系统 PATH）
- 依赖库：PySide6, send2trash

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 安装 FFmpeg

从 [FFmpeg 官网](https://ffmpeg.org/download.html) 下载，将 `bin` 目录添加到系统 PATH 中。

验证安装：

```bash
ffmpeg -version
ffprobe -version
```

### 3. 运行程序

```bash
set PYTHONPATH=%CD%\src
python src/fisheep_video_merger/main.py
```

或者在 VS Code 中按 `F5` 使用已配置的调试启动项运行。

## 使用说明

1. **添加文件夹** — 点击"添加文件夹"按钮或拖拽文件夹到窗口
2. **自动扫描** — 程序自动扫描 m4s 文件并分析流类型，自动配对后填入合并队列
3. **勾选任务** — 在合并队列中勾选需要合并的任务（默认全部勾选）
4. **设置参数** — 选择输出格式和输出目录
5. **开始合并** — 点击"开始合并"按钮，等待处理完成

### 集数命名规则

如果源文件名包含集数信息，输出文件会自动添加编号后缀：

| 源文件中的集数格式 | 输出文件名示例 |
|---|---|
| `第3集` | `番名_03.mp4` |
| `第四集` | `番名_04.mp4` |
| `EP03` / `E10` | `番名_03.mp4` |
| `#05` | `番名_05.mp4` |

## 项目结构

```
src/fisheep_video_merger/
├── main.py              # 程序入口
├── core/
│   ├── scanner.py       # 文件扫描器
│   ├── matcher.py       # 自动配对逻辑
│   ├── merger.py        # FFmpeg 合并引擎
│   └── path_utils.py    # 路径工具
├── ui/
│   ├── main_window.py   # 主窗口
│   ├── settings_panel.py # 设置面板
│   ├── merge_queue_tab.py # 合并队列标签页
│   ├── pending_tab.py   # 待处理标签页
│   └── dialogs.py       # 对话框
└── utils/
    ├── ffprobe.py       # ffprobe 封装
    └── logger.py        # 日志工具
```

## 许可证

MIT
