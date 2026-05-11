"""
程序入口
"""

import sys
import os

from PySide6.QtWidgets import QApplication, QMessageBox
from PySide6.QtCore import Qt

from fisheep_video_merger import __appname__, __version__
from fisheep_video_merger.ui.main_window import MainWindow
from fisheep_video_merger.utils.ffprobe import check_ffmpeg_available
from fisheep_video_merger.utils.logger import setup_logger, get_logger


def main():
    """主函数"""
    # 初始化日志
    log_dir = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "..", "..", "logs",
    )
    setup_logger(log_dir)
    logger = get_logger()
    logger.info(f"启动 {__appname__} v{__version__}")

    # 创建应用
    app = QApplication(sys.argv)
    app.setApplicationName(__appname__)
    app.setApplicationVersion(__version__)

    # 检查 ffmpeg
    if not check_ffmpeg_available():
        logger.warning("ffmpeg/ffprobe 未检测到")
        QMessageBox.warning(
            None,
            "ffmpeg 未找到",
            "未检测到 ffmpeg/ffprobe，请确保已安装 ffmpeg 并加入系统 PATH。\n\n"
            "合并功能将被禁用，但您仍可使用扫描和配对功能。",
        )

    # 创建并显示主窗口
    window = MainWindow()
    window.show()

    logger.info("主窗口已显示")

    # 运行应用
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
