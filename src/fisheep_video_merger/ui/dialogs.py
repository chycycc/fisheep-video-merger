"""
对话框模块
包含批量命名、重名处理、删除确认、结果摘要等对话框
"""

from typing import Optional

from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QSpinBox,
    QPushButton,
    QCheckBox,
    QDialogButtonBox,
    QMessageBox,
    QFormLayout,
)
from PySide6.QtCore import Qt


class BatchRenameDialog(QDialog):
    """批量命名对话框"""

    def __init__(self, count: int, parent=None):
        super().__init__(parent)
        self.setWindowTitle("批量命名")
        self.setMinimumWidth(350)

        layout = QFormLayout(self)

        # 前缀
        self.prefix_edit = QLineEdit()
        self.prefix_edit.setPlaceholderText("输入前缀文字...")
        layout.addRow("前缀:", self.prefix_edit)

        # 起始序号
        self.start_spin = QSpinBox()
        self.start_spin.setRange(1, 9999)
        self.start_spin.setValue(1)
        layout.addRow("起始序号:", self.start_spin)

        # 序号位数
        self.digits_spin = QSpinBox()
        self.digits_spin.setRange(1, 6)
        self.digits_spin.setValue(2)
        layout.addRow("序号位数:", self.digits_spin)

        # 预览
        self.preview_label = QLabel()
        self.preview_label.setStyleSheet("color: gray;")
        layout.addRow("预览:", self.preview_label)

        # 连接信号更新预览
        self.prefix_edit.textChanged.connect(self.update_preview)
        self.start_spin.valueChanged.connect(self.update_preview)
        self.digits_spin.valueChanged.connect(self.update_preview)

        # 按钮
        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

        self.update_preview()

    def update_preview(self):
        """更新命名预览"""
        prefix = self.prefix_edit.text() or "前缀"
        digits = self.digits_spin.value()
        start = self.start_spin.value()
        preview = f"{prefix}_{start:0{digits}d}, {prefix}_{start + 1:0{digits}d}, ..."
        self.preview_label.setText(preview)

    def get_result(self) -> tuple[str, int, int]:
        """获取结果 (前缀, 起始序号, 序号位数)"""
        return (
            self.prefix_edit.text(),
            self.start_spin.value(),
            self.digits_spin.value(),
        )


class ConflictDialog(QDialog):
    """文件重名冲突处理对话框"""

    def __init__(self, filepath: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("文件已存在")
        self.setMinimumWidth(450)

        layout = QVBoxLayout(self)

        # 提示信息
        msg = QLabel(f"输出文件已存在:\n{filepath}\n\n请选择处理方式：")
        msg.setWordWrap(True)
        layout.addWidget(msg)

        # 应用到全部
        self.apply_all_cb = QCheckBox("本次合并全部采用此选择")
        layout.addWidget(self.apply_all_cb)

        # 按钮
        btn_layout = QHBoxLayout()

        self.overwrite_btn = QPushButton("覆盖")
        self.rename_btn = QPushButton("自动重命名")
        self.skip_btn = QPushButton("跳过")

        btn_layout.addWidget(self.overwrite_btn)
        btn_layout.addWidget(self.rename_btn)
        btn_layout.addWidget(self.skip_btn)

        layout.addLayout(btn_layout)

        self.overwrite_btn.clicked.connect(lambda: self.done(1))
        self.rename_btn.clicked.connect(lambda: self.done(2))
        self.skip_btn.clicked.connect(lambda: self.done(3))

    def is_apply_all(self) -> bool:
        """是否应用到全部"""
        return self.apply_all_cb.isChecked()


class DeleteConfirmDialog(QDialog):
    """删除源文件确认对话框"""

    def __init__(self, file_count: int, parent=None):
        super().__init__(parent)
        self.setWindowTitle("确认删除源文件")
        self.setMinimumWidth(400)

        layout = QVBoxLayout(self)

        msg = QLabel(
            f"所有成功合并的源文件（共 {file_count} 个）将被移至回收站。\n\n"
            "此操作不可撤销，确定要继续吗？"
        )
        msg.setWordWrap(True)
        layout.addWidget(msg)

        buttons = QDialogButtonBox(
            QDialogButtonBox.Yes | QDialogButtonBox.No
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)


class ResultSummaryDialog(QDialog):
    """合并结果摘要对话框"""

    def __init__(self, success_count: int, fail_count: int, parent=None):
        super().__init__(parent)
        self.setWindowTitle("合并完成")
        self.setMinimumWidth(350)

        layout = QVBoxLayout(self)

        icon = "✅" if fail_count == 0 else "⚠️"
        msg = QLabel(
            f"{icon} 合并完成！\n\n"
            f"成功: {success_count} 个\n"
            f"失败: {fail_count} 个"
        )
        msg.setAlignment(Qt.AlignCenter)
        msg.setStyleSheet("font-size: 14px;")
        layout.addWidget(msg)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok)
        buttons.accepted.connect(self.accept)
        layout.addWidget(buttons)


class NameInputDialog(QDialog):
    """手动配对时输入输出文件名对话框"""

    def __init__(self, video_name: str, audio_name: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("输入输出文件名")
        self.setMinimumWidth(400)

        layout = QVBoxLayout(self)

        info = QLabel(
            f"视频: {video_name}\n"
            f"音频: {audio_name}\n\n"
            "请输入输出文件名（不含扩展名）："
        )
        info.setWordWrap(True)
        layout.addWidget(info)

        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("输入文件名...")
        layout.addWidget(self.name_edit)

        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def get_name(self) -> str:
        """获取输入的文件名"""
        return self.name_edit.text().strip()
