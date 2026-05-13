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

        # === 组1.5：界面主题 ===
        theme_group = QGroupBox("界面主题")
        theme_layout = QVBoxLayout(theme_group)

        self.theme_combo = QComboBox()
        self.theme_combo.addItems(["跟随系统", "明亮模式", "深色护眼"])
        self.theme_combo.setCurrentIndex(0)
        self.theme_combo.currentIndexChanged.connect(lambda: self.settings_changed.emit())
        theme_layout.addWidget(self.theme_combo)

        layout.addWidget(theme_group)

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

        # === 组3.5：选中项目输出详情 (U-3 & 联动: 动态展示，无选中时折叠) ===
        self.detail_group = QGroupBox("📌 选中项目输出详情")
        detail_layout = QVBoxLayout(self.detail_group)
        
        self.detail_title = QLabel("📍 预计输出绝对路径：")
        self.detail_title.setStyleSheet("font-size: 11px; color: gray;")
        detail_layout.addWidget(self.detail_title)

        self.detail_path_label = QLabel("")
        self.detail_path_label.setWordWrap(True)
        self.detail_path_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.detail_path_label.setStyleSheet(
            "QLabel {"
            "   background-color: palette(base);"  # 智能适配深/浅主题输入框基底色
            "   border: 1px solid palette(mid);"
            "   border-radius: 4px;"
            "   padding: 8px;"
            "   font-size: 11px;"
            "   font-family: Consolas, 'Courier New';"
            "}"
        )
        detail_layout.addWidget(self.detail_path_label)
        
        detail_btn_row = QHBoxLayout()
        self.copy_path_btn = QPushButton("📋 复制全路径")
        self.copy_path_btn.setStyleSheet("font-size: 11px; height: 22px;")
        self.copy_path_btn.clicked.connect(self._on_copy_path)
        detail_btn_row.addWidget(self.copy_path_btn)
        
        self.open_dir_btn = QPushButton("📂 浏览所在文件夹")
        self.open_dir_btn.setStyleSheet("font-size: 11px; height: 22px;")
        self.open_dir_btn.clicked.connect(self._on_open_dir)
        detail_btn_row.addWidget(self.open_dir_btn)
        
        detail_layout.addLayout(detail_btn_row)
        
        layout.addWidget(self.detail_group)
        self.detail_group.setVisible(False) # 缺省不选时隐藏
        
        self._current_detail_path = ""

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

    def get_theme(self) -> str:
        """获取选中的外观主题：system / light / dark"""
        # 返回映射到持久化存储的底层键名
        return ["system", "light", "dark"][self.theme_combo.currentIndex()]

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
            "theme": self.get_theme(),
        }

    def load_settings_dict(self, data: dict):
        """载入所有设置项"""
        # 阻止信号发射避免干扰恢复流程
        self.blockSignals(True)
        try:
            fmt = data.get("output_format", "mp4").lower()
            idx = self.format_combo.findText(fmt)
            if idx >= 0:
                self.format_combo.setCurrentIndex(idx)
            
            self.dir_edit.setText(data.get("output_dir", ""))
            
            self.delete_cb.setChecked(bool(data.get("delete_allowed", False)))

            # 载入主题状态
            saved_theme = data.get("theme", "system")
            theme_mapping = {"system": 0, "light": 1, "dark": 2}
            self.theme_combo.setCurrentIndex(theme_mapping.get(saved_theme, 0))
        finally:
            self.blockSignals(False)

    def _on_copy_path(self):
        """复制当前选中的绝对路径到剪贴板"""
        if self._current_detail_path:
            from PySide6.QtWidgets import QApplication
            QApplication.clipboard().setText(self._current_detail_path)

    def _on_open_dir(self):
        """在文件资源管理器中浏览并打开该路径所在文件夹"""
        if self._current_detail_path:
            folder = os.path.dirname(self._current_detail_path)
            if os.path.exists(folder):
                os.startfile(folder)

    def update_task_detail(self, full_path: str):
        """更新右侧栏的任务详情卡片显示内容 (联动响应)"""
        if full_path:
            self._current_detail_path = os.path.abspath(full_path)
            self.detail_path_label.setText(self._current_detail_path)
            self.detail_group.setVisible(True)
        else:
            self._current_detail_path = ""
            self.detail_group.setVisible(False)
