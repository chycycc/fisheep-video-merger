"""
设置面板模块
右侧设置面板，包含输出格式、输出目录、源文件处理等设置
"""

import os
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QComboBox,
    QLineEdit,
    QPushButton,
    QCheckBox,
    QFileDialog,
)
from PySide6.QtCore import Signal


class SettingsPanel(QWidget):
    """右侧设置面板"""

    # 信号：开始合并按钮被点击
    start_merge_clicked = Signal()
    # 信号：设置发生变化
    settings_changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumWidth(280)
        self.setMaximumWidth(380)
        self._setup_ui()

    def _setup_ui(self):
        """初始化界面"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)

        # === 组1：输出格式 ===
        format_group = QGroupBox("输出格式")
        format_layout = QVBoxLayout(format_group)

        self.format_combo = QComboBox()
        self.format_combo.addItems(["mp4", "mkv", "mov", "flv"])
        self.format_combo.setCurrentText("mp4")
        self.format_combo.currentTextChanged.connect(lambda: self.settings_changed.emit())
        format_layout.addWidget(self.format_combo)

        layout.addWidget(format_group)

        # === 组2：输出目录 ===
        dir_group = QGroupBox("输出目录")
        dir_layout = QVBoxLayout(dir_group)

        dir_label = QLabel("统一输出到：")
        dir_layout.addWidget(dir_label)

        dir_input_layout = QHBoxLayout()
        self.dir_edit = QLineEdit()
        self.dir_edit.setPlaceholderText("选择输出目录...")
        self.dir_edit.textChanged.connect(lambda: self.settings_changed.emit())
        dir_input_layout.addWidget(self.dir_edit)

        self.browse_btn = QPushButton("浏览...")
        self.browse_btn.clicked.connect(self._browse_output_dir)
        dir_input_layout.addWidget(self.browse_btn)

        dir_layout.addLayout(dir_input_layout)

        dir_hint = QLabel("合并后的视频将统一输出到该目录下")
        dir_hint.setWordWrap(True)
        dir_hint.setStyleSheet("color: gray; font-size: 11px;")
        dir_layout.addWidget(dir_hint)

        layout.addWidget(dir_group)

        # === 组3：源文件处理 ===
        source_group = QGroupBox("源文件处理")
        source_layout = QVBoxLayout(source_group)

        self.delete_cb = QCheckBox("合并成功后允许删除原始 m4s 文件")
        source_layout.addWidget(self.delete_cb)

        delete_hint = QLabel("仅当勾选且合并全部成功后，会再次询问确认")
        delete_hint.setWordWrap(True)
        delete_hint.setStyleSheet("color: gray; font-size: 11px;")
        source_layout.addWidget(delete_hint)

        layout.addWidget(source_group)

        # === 组4：操作按钮 ===
        action_group = QGroupBox()
        action_layout = QVBoxLayout(action_group)

        self.start_btn = QPushButton("▶ 开始合并")
        self.start_btn.setMinimumHeight(40)
        self.start_btn.setStyleSheet(
            "QPushButton { font-size: 14px; font-weight: bold; "
            "background-color: #4CAF50; color: white; border-radius: 5px; }"
            "QPushButton:hover { background-color: #45a049; }"
            "QPushButton:disabled { background-color: #cccccc; color: #888888; }"
        )
        self.start_btn.clicked.connect(self.start_merge_clicked.emit)
        self.start_btn.setEnabled(False)
        action_layout.addWidget(self.start_btn)

        self.status_label = QLabel("请先添加文件夹并完成配对")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setStyleSheet("color: gray; font-size: 11px;")
        action_layout.addWidget(self.status_label)

        layout.addWidget(action_group)

        # 弹簧，将内容推到顶部
        layout.addStretch()

    def _browse_output_dir(self):
        """浏览选择输出目录"""
        directory = QFileDialog.getExistingDirectory(
            self, "选择输出目录",
            self.dir_edit.text() or os.path.expanduser("~"),
        )
        if directory:
            self.dir_edit.setText(directory)

    def get_output_format(self) -> str:
        """获取输出格式"""
        return self.format_combo.currentText()

    def get_output_dir(self) -> str:
        """获取输出目录"""
        return self.dir_edit.text().strip()

    def is_delete_allowed(self) -> bool:
        """是否允许删除源文件"""
        return self.delete_cb.isChecked()

    def set_status(self, text: str, is_error: bool = False):
        """设置状态文本"""
        self.status_label.setText(text)
        if is_error:
            self.status_label.setStyleSheet("color: red; font-size: 11px;")
        else:
            self.status_label.setStyleSheet("color: gray; font-size: 11px;")

    def set_start_enabled(self, enabled: bool):
        """设置开始合并按钮是否可用"""
        self.start_btn.setEnabled(enabled)

    def get_settings_dict(self) -> dict:
        """获取所有设置项"""
        return {
            "output_format": self.get_output_format(),
            "output_dir": self.get_output_dir(),
            "delete_allowed": self.is_delete_allowed(),
        }
