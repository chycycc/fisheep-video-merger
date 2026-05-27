"""
🐑 B站 m4s 视频合并工具 v0.4.0 - PyWebview 桌面窗口主入口
100% 剥离 PySide 依赖，使用系统级原生 Chromium (Edge WebView2) 核心渲染 Web 视觉
与原有业务逻辑、日志系统以及工作区状态文件无缝衔接
"""

import sys
import os
import webview

from fisheep_video_merger import __appname__, __version__
from fisheep_video_merger.utils.bridge import UIBridge
from fisheep_video_merger.utils.ffprobe import check_ffmpeg_available
from fisheep_video_merger.utils.logger import setup_logger, get_logger

logger = get_logger()


def main():
    """Webview 运行入口"""
    # 1. 初始化日志目录 (自动适配 PyInstaller 打包环境与源码开发环境)
    if getattr(sys, "frozen", False):
        # 运行在打包后的单 EXE 中，日志文件夹生成在 EXE 同级目录下
        base_dir = os.path.dirname(sys.executable)
        log_dir = os.path.join(base_dir, "logs")
    else:
        # 源码开发环境运行，存放在 src 同级父目录的 logs 目录中
        base_dir = os.path.dirname(os.path.abspath(__file__))
        log_dir = os.path.abspath(os.path.join(base_dir, "..", "..", "logs"))

    setup_logger(log_dir)
    logger = get_logger()
    logger.info(f"启动 PyWebview 版 {__appname__} v{__version__}")

    # 2. 检查 FFmpeg 环境可用性
    ffmpeg_available = check_ffmpeg_available()
    if not ffmpeg_available:
        logger.warning("后台未检测到 ffmpeg/ffprobe 依赖")

    # 3. 创建 Python-JS 双向桥接实例
    bridge = UIBridge()

    # 4. 定位本地 HTML 资源文件路径 (考虑 PyInstaller 静态资源解压路径)
    current_dir = os.path.dirname(os.path.abspath(__file__))
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        # 在 PyInstaller 单文件打包运行中，静态网页解压至临时目录中
        html_path = os.path.join(sys._MEIPASS, "fisheep_video_merger", "ui", "web", "index.html")
    else:
        # 在常规源码开发环境下运行
        html_path = os.path.join(current_dir, "ui", "web", "index.html")

    if not os.path.exists(html_path):
        logger.error(f"无法定位前端资源 HTML 文件: {html_path}")
        sys.exit(1)

    url = "file:///" + os.path.abspath(html_path)
    logger.info(f"正在加载本地网页资源: {url}")

    # 5. 拉起高颜值桌面窗口 (Edge WebView2)
    # 从设置中恢复窗口位置
    s = bridge.settings
    window = webview.create_window(
        title=f"{__appname__} v{__version__} - 极速美化 WebView2 版 🐑",
        url=url,
        js_api=bridge,
        width=s.get("window_width", 1100),
        height=s.get("window_height", 700),
        x=s.get("window_x"),
        y=s.get("window_y"),
        min_size=(800, 600),
        resizable=True,
        text_select=True,
    )

    # 将 window 句柄反向挂载入桥，以便后台线程主动 evaluate_js 回传进度
    bridge.set_window(window)

    # 窗口关闭处理：保存状态 + 保存窗口位置 + 终止 FFmpeg 进程
    def on_window_closed():
        logger.info("窗口关闭，正在清理...")
        # 保存窗口位置
        try:
            bridge.settings["window_x"] = window.x
            bridge.settings["window_y"] = window.y
            bridge.settings["window_width"] = window.width
            bridge.settings["window_height"] = window.height
        except Exception:
            pass
        bridge.cancel_merging()
        bridge._save_workspace_state()
        logger.info("清理完成")

    window.events.closed += on_window_closed

    # 6. 运行 webview 主循环
    webview.start(debug=False)


if __name__ == "__main__":
    main()
