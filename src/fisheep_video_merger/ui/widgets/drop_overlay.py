"""
毛玻璃拖拽蒙层控件
当用户拖拽文件/文件夹进入窗口时淡入显示，提供高颜值的视觉反馈
"""

from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QFrame
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QFont, QColor


class DropOverlay(QWidget):
    """全窗口覆盖的拖拽蒙层控件"""

    def __init__(self, parent=None):
        super().__init__(parent)
        
        # 核心属性：对鼠标和拖拽事件完全穿透，让底层 MainWindow 统一处理拖放逻辑
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.setVisible(False)
        
        self._setup_ui()

    def _setup_ui(self):
        """初始化界面与高级 QSS 样式表"""
        # 主布局：居中填充
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(40, 40, 40, 40)
        
        # 外边框容器：实现带虚线边框的磨砂玻璃盒子
        self.border_frame = QFrame()
        self.border_frame.setObjectName("DropBorderFrame")
        
        frame_layout = QVBoxLayout(self.border_frame)
        frame_layout.setAlignment(Qt.AlignCenter)
        frame_layout.setSpacing(15)
        
        # 🐑 羊驼大图标
        self.icon_label = QLabel("🐑")
        self.icon_label.setAlignment(Qt.AlignCenter)
        self.icon_label.setStyleSheet("font-size: 72px; background: transparent;")
        frame_layout.addWidget(self.icon_label)
        
        # 引导文案
        self.text_label = QLabel("释放鼠标，立即导入视频合并任务")
        self.text_label.setObjectName("DropTextLabel")
        self.text_label.setAlignment(Qt.AlignCenter)
        self.text_label.setWordWrap(True)
        frame_layout.addWidget(self.text_label)
        
        main_layout.addWidget(self.border_frame)
        
        # 应用高阶样式表 (支持暗色与明亮模式的科技透感)
        self.setStyleSheet("""
            DropOverlay {
                background-color: rgba(30, 30, 45, 195);
            }
            QFrame#DropBorderFrame {
                border: 2px dashed #4CAF50;
                border-radius: 12px;
                background-color: rgba(255, 255, 255, 10);
            }
            QLabel#DropTextLabel {
                color: #4CAF50;
                font-size: 20px;
                font-weight: bold;
                font-family: "Segoe UI", "Microsoft YaHei", sans-serif;
                background: transparent;
            }
        """)

    def set_theme(self, is_dark: bool):
        """根据主题调整蒙层的背景透度与文字发光色"""
        if is_dark:
            self.setStyleSheet("""
                DropOverlay {
                    background-color: rgba(20, 20, 30, 200);
                }
                QFrame#DropBorderFrame {
                    border: 2px dashed #4CAF50;
                    border-radius: 12px;
                    background-color: rgba(255, 255, 255, 8);
                }
                QLabel#DropTextLabel {
                    color: #4CAF50;
                    font-size: 20px;
                    font-weight: bold;
                    font-family: "Segoe UI", "Microsoft YaHei", sans-serif;
                    background: transparent;
                }
            """)
        else:
            self.setStyleSheet("""
                DropOverlay {
                    background-color: rgba(240, 240, 245, 205);
                }
                QFrame#DropBorderFrame {
                    border: 2px dashed #2E7D32;
                    border-radius: 12px;
                    background-color: rgba(0, 0, 0, 8);
                }
                QLabel#DropTextLabel {
                    color: #2E7D32;
                    font-size: 20px;
                    font-weight: bold;
                    font-family: "Segoe UI", "Microsoft YaHei", sans-serif;
                    background: transparent;
                }
            """)
