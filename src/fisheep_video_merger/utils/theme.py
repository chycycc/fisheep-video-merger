"""
主题样式模块
基于原生 QPalette 和 Fusion 样式，实现极致流畅的明亮/深色主题以及跟随系统动态切换
"""

from PySide6.QtGui import QPalette, QColor, QGuiApplication
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication


def apply_theme(theme_mode: str):
    """
    根据指定的主题字符串实时更新全局 App 的界面主题配色
    Args:
        theme_mode: 'system' (跟随系统) | 'light' (强制定制明亮) | 'dark' (深色极客)
    """
    app = QApplication.instance()
    if not app:
        return

    # 1. 确定最终生效的是否是深色环境
    is_dark = False
    if theme_mode == "dark":
        is_dark = True
    elif theme_mode == "system":
        try:
            # Qt 6.5+ 原生风格嗅探，支持 Win10/11 与 macOS 系统级深色状态感知
            is_dark = (QGuiApplication.styleHints().colorScheme() == Qt.ColorScheme.Dark)
        except Exception:
            is_dark = False

    # 2. 应用对应的 Palette 和微调 QSS
    if is_dark:
        # 设置跨平台融合风格，保证黑暗调色盘完美且精致地作用于每一个角落
        app.setStyle("Fusion")

        palette = QPalette()
        
        # 调色板色彩定义（精致深灰：#1e1e1e，文字：浅灰白）
        win_color = QColor(30, 30, 30)
        base_color = QColor(22, 22, 22)
        alt_color = QColor(40, 40, 40)
        txt_color = QColor(220, 220, 220)
        hl_color = QColor(42, 110, 180)  # 亮蓝色高亮

        palette.setColor(QPalette.Window, win_color)
        palette.setColor(QPalette.WindowText, txt_color)
        palette.setColor(QPalette.Base, base_color)
        palette.setColor(QPalette.AlternateBase, alt_color)
        palette.setColor(QPalette.ToolTipBase, win_color)
        palette.setColor(QPalette.ToolTipText, txt_color)
        palette.setColor(QPalette.Text, txt_color)
        palette.setColor(QPalette.Button, win_color)
        palette.setColor(QPalette.ButtonText, txt_color)
        palette.setColor(QPalette.BrightText, Qt.red)
        palette.setColor(QPalette.Link, hl_color)
        palette.setColor(QPalette.Highlight, hl_color)
        palette.setColor(QPalette.HighlightedText, Qt.white)

        # 针对 Disable（不可用）控件置灰，防止界面混乱
        gray_out = QColor(100, 100, 100)
        palette.setColor(QPalette.Disabled, QPalette.WindowText, gray_out)
        palette.setColor(QPalette.Disabled, QPalette.Text, gray_out)
        palette.setColor(QPalette.Disabled, QPalette.ButtonText, gray_out)

        app.setPalette(palette)

        # 3. 加载少量全局 QSS 以微调原生控件（如滚动条圆角、表格栅格、Tab栏边框）
        app.setStyleSheet("""
            /* 修复 Tooltip 在黑暗底色下的边框 */
            QToolTip { color: #ffffff; background-color: #252525; border: 1px solid #555555; padding: 2px; }
            
            /* 精致化表格表头 */
            QHeaderView::section { background-color: #2a2a2a; color: #dddddd; border: 1px solid #3e3e3e; padding: 4px; }
            QTableWidget { gridline-color: #3a3a3a; background-color: #161616; alternate-background-color: #202020; }
            
            /* 统一圆角滑块滚动条，彻底去除复古感 */
            QScrollBar:vertical { background: #1e1e1e; width: 10px; margin: 0px; border-radius: 5px; }
            QScrollBar::handle:vertical { background: #4e4e4e; min-height: 20px; border-radius: 5px; }
            QScrollBar::handle:vertical:hover { background: #666666; }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }
            QScrollBar:horizontal { background: #1e1e1e; height: 10px; margin: 0px; border-radius: 5px; }
            QScrollBar::handle:horizontal { background: #4e4e4e; min-width: 20px; border-radius: 5px; }
            QScrollBar::handle:horizontal:hover { background: #666666; }
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0px; }
            
            /* 美化侧边 Tab 切换器 */
            QTabWidget::pane { border: 1px solid #3a3a3a; top: -1px; background-color: #1e1e1e; }
            QTabBar::tab { background: #252525; color: #a0a0a0; border: 1px solid #3a3a3a; padding: 8px 16px; border-bottom-color: transparent; border-top-left-radius: 4px; border-top-right-radius: 4px; }
            QTabBar::tab:selected { background: #1e1e1e; color: #ffffff; border-bottom-color: #1e1e1e; font-weight: bold; }
            QTabBar::tab:hover:!selected { background: #333333; color: #cccccc; }
            
            /* 优化输入框与按钮 */
            QLineEdit { background-color: #262626; border: 1px solid #444444; border-radius: 3px; padding: 3px; color: #e0e0e0; }
            QLineEdit:focus { border: 1px solid #2a6eb4; }
            QComboBox { background-color: #262626; border: 1px solid #444444; border-radius: 3px; padding: 3px 15px 3px 3px; color: #e0e0e0; }
            QComboBox::drop-down { border: none; }
            QGroupBox { border: 1px solid #3a3a3a; margin-top: 12px; border-radius: 4px; font-weight: bold; }
            QGroupBox::title { subcontrol-origin: margin; left: 8px; padding: 0 3px; color: #aaaaaa; }
        """)
    else:
        # 恢复系统原生默认明亮调色板与清除注入式 QSS 样式
        app.setPalette(QPalette())
        app.setStyleSheet("")
        # 清空显式设置的 style 以退回到操作系统默认的风格（如 windowsvista/macos）
        app.setStyle("")
