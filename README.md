# 🐑 Fisheep Video Merger

<p align="center">
  <img src="https://img.shields.io/badge/Version-v0.2.0-brightgreen?style=for-the-badge" alt="Version">
  <img src="https://img.shields.io/badge/Platform-Windows_10%2B-blue?style=for-the-badge&logo=windows" alt="Platform">
  <img src="https://img.shields.io/badge/License-MIT-orange?style=for-the-badge" alt="License">
</p>

`Fisheep Video Merger` 是一款专为 Windows 用户打造的高颜值、工业级桌面合并工具。它能帮助您以优雅、极智的姿态，秒级批量合并 B站（Bilibili）缓存的 m4s 分离式音视频文件！

---

## 🚀 核心交互革命 (v0.2.0 新增)

*   **📐 极智黄金皮筋自适应**：废除传统表格的空间霸权。主界面表格的「输出文件名」与「关联源文件」列以 **50:50 完美比例**等宽呼吸拉伸，带来极致平衡的视觉观感。
*   **📂 右侧看板物理收纳**：表格拒绝臃肿！全面砍掉冗余路径列，首创右侧高内聚设置面板。当您点击任何任务，右侧会自动升起一个**代码风格微圆角浅灰（自适应深色主题）的绝对路径详情盒**，支持快捷复制。
*   **↔️ 一键物理侧栏折叠**：点击折叠按钮瞬间让侧栏物理隐形，将界面 100% 的舞台空间让位给数据表格，视界最大化。
*   **🧹 颗粒度清理选择柜**：不再有“一刀切”的粗野操作。清空时自动升起复选台，支持按需分离清理合并队列、待整理、已完整缓存或导入源文件夹痕迹。

---

## 💎 核心基本功

*   🔍 **递归深度扫描**：一键导入文件夹，多线程级智能递归，自动剥离音频（Audio）、视频（Video）与封装完毕的（Muxed）文件。
*   🤖 **孪生对除噪配对**：强悍的中文/英文双引擎防务正则。不仅能按字典序丝滑配对多集文件，更能智能防范过度去噪，完美保留 `_bilibili` 等核心命名语义。
*   🧠 **文件名嗅探博弈**：手动配对时智能探测！纯数字垃圾命名自动退回捕获父级目录名；语义中文名则智能裁剪，给您最完美的推荐默认名。
*   ⚡ **流式极速转封装**：对于已被合并的 muxed 文件，支持一键无损剥离重封为 mp4 / mkv 格式。
*   🗑️ **物理级防误删锁**：支持将源文件安全投递至系统回收站（send2trash），绝不暴力直接抹除。

---

## 📥 快速享用（两分钟开箱）

### 🌟 方案 A：绿色免安装一键启动（🔥 极力推荐！）
无需安装 Python，无需任何复杂配置。
1. 点击项目右侧的 👉 [**Releases**](https://github.com/chycycc/fisheep-video-merger/releases) 页面。
2. 下载最新版正式编译产物 `FisheepVideoMerger.exe` (约 50MB)。
3. 双击即可瞬间启动！*(注：系统需安装 FFmpeg 并加入环境变量)*。

### 🐍 方案 B：从源码运行（开发者模式）
若您希望基于源码进行二次开发或深度调测：
```bash
# 1. 克隆仓库并进入目录
git clone https://github.com/chycycc/fisheep-video-merger.git
cd fisheep-video-merger

# 2. 安装依赖
pip install -r requirements.txt

# 3. 运行主程序
$env:PYTHONPATH="src"; python src/fisheep_video_merger/main.py
```

---

## 📦 项目架构图

```text
src/fisheep_video_merger/
├── core/
│   ├── scanner.py       # 多线程文件扫描引擎
│   ├── matcher.py       # 中文除噪配对博弈算法
│   ├── merger.py        # FFmpeg 流式执行管线
├── ui/
│   ├── main_window.py   # 黄金布局核心主窗体
│   ├── settings_panel.py # 侧栏与路径看板盒
│   └── dialogs.py       # 颗粒度清理确认台
└── utils/
    ├── ffprobe.py       # 流分析原子层
    └── logger.py        # 终端适配双轨日志
```

---
MIT License © 2026 Fisheep Team.
