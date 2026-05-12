"""
muxed 文件标签页
显示已包含音视频的完整 m4s 文件，支持转封装操作
"""

import os
from typing import Optional

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QAbstractItemView,
    QMenu,
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QAction

from fisheep_video_merger.utils.ffprobe import StreamInfo


class MuxedTab(QWidget):
    """已完整文件标签页"""

    preview_requested = Signal(str)  # 请求预览
    remux_requested = Signal(list)   # 请求转封装选中文件
    tasks_changed = Signal()

    COL_CHECK = 0      # 选择框
    COL_STATUS = 1     # 状态
    COL_FILENAME = 2   # 文件名
    COL_CODECS = 3     # 编码格式
    COL_OUTPUT = 4     # 预计输出路径

    HEADERS = ["", "状态", "文件名", "编码", "预计输出路径"]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.infos: list[StreamInfo] = []
        self.statuses: dict[str, str] = {}  # filepath -> "pending"/"success"/"error"
        self._setup_ui()

    def _setup_ui(self):
        """初始化界面"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.table = QTableWidget()
        self.table.setColumnCount(len(self.HEADERS))
        self.table.setHorizontalHeaderLabels(self.HEADERS)

        header = self.table.horizontalHeader()
        header.setSectionResizeMode(self.COL_CHECK, QHeaderView.Fixed)
        self.table.setColumnWidth(self.COL_CHECK, 30)
        header.setSectionResizeMode(self.COL_STATUS, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(self.COL_FILENAME, QHeaderView.Stretch)
        header.setSectionResizeMode(self.COL_CODECS, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(self.COL_OUTPUT, QHeaderView.Stretch)

        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.table.setAlternatingRowColors(True)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)

        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._show_context_menu)

        layout.addWidget(self.table)

    def set_files(self, infos: list[StreamInfo]):
        """设置文件列表"""
        self.infos = infos
        for info in infos:
            if info.filepath not in self.statuses:
                self.statuses[info.filepath] = "pending"
        self._refresh_table()

    def clear(self):
        """清空列表"""
        self.infos.clear()
        self.statuses.clear()
        self._refresh_table()

    def set_status(self, filepath: str, status: str):
        """设置单个文件状态"""
        self.statuses[filepath] = status
        self._refresh_table()

    def get_checked_indices(self) -> list[int]:
        """获取勾选的行索引"""
        indices = []
        for row in range(self.table.rowCount()):
            item = self.table.item(row, self.COL_CHECK)
            if item and item.checkState() == Qt.Checked:
                indices.append(row)
        return indices

    def get_file_count(self) -> int:
        """获取文件数量"""
        return len(self.infos)

    def _refresh_table(self):
        """刷新表格显示"""
        self.table.blockSignals(True)
        self.table.setRowCount(len(self.infos))

        for i, info in enumerate(self.infos):
            # 选择框
            check_item = QTableWidgetItem("")
            check_item.setFlags(
                Qt.ItemIsUserCheckable | Qt.ItemIsEnabled | Qt.ItemIsSelectable
            )
            status = self.statuses.get(info.filepath, "pending")
            check_item.setCheckState(
                Qt.Checked if status == "pending" else Qt.Unchecked
            )
            check_item.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(i, self.COL_CHECK, check_item)

            # 状态
            status_text = {"pending": "⬜", "success": "✅", "error": "❌"}.get(
                status, "⬜"
            )
            status_item = QTableWidgetItem(status_text)
            status_item.setTextAlignment(Qt.AlignCenter)
            status_item.setFlags(status_item.flags() & ~Qt.ItemIsEditable)
            self.table.setItem(i, self.COL_STATUS, status_item)

            # 文件名
            name_item = QTableWidgetItem(os.path.basename(info.filepath))
            name_item.setToolTip(info.filepath)
            name_item.setFlags(name_item.flags() & ~Qt.ItemIsEditable)
            self.table.setItem(i, self.COL_FILENAME, name_item)

            # 编码
            codecs = []
            if info.video_codec:
                codecs.append(f"V:{info.video_codec}")
            if info.audio_codec:
                codecs.append(f"A:{info.audio_codec}")
            codec_text = " ".join(codecs) if codecs else "—"
            codec_item = QTableWidgetItem(codec_text)
            codec_item.setTextAlignment(Qt.AlignCenter)
            codec_item.setFlags(codec_item.flags() & ~Qt.ItemIsEditable)
            self.table.setItem(i, self.COL_CODECS, codec_item)

            # 输出路径（先留空，由外部更新）
            path_item = QTableWidgetItem("")
            path_item.setFlags(path_item.flags() & ~Qt.ItemIsEditable)
            self.table.setItem(i, self.COL_OUTPUT, path_item)

        self.table.blockSignals(False)

    def update_output_paths(self, paths: list[str]):
        """更新预计输出路径列"""
        self.table.blockSignals(True)
        for i, path in enumerate(paths):
            if i < self.table.rowCount():
                item = self.table.item(i, self.COL_OUTPUT)
                if item:
                    item.setText(path)
                    item.setToolTip(path)
        self.table.blockSignals(False)

    def _show_context_menu(self, pos):
        """显示右键菜单"""
        checked = self.get_checked_indices()
        if not checked:
            return

        menu = QMenu(self)

        # 转封装
        remux_action = QAction("🔧 转封装为输出格式", self)
        remux_action.triggered.connect(
            lambda: self.remux_requested.emit(checked)
        )
        menu.addAction(remux_action)

        # 预览
        if len(checked) == 1 and checked[0] < len(self.infos):
            preview_action = QAction("👁️ 预览", self)
            preview_action.triggered.connect(
                lambda: self.preview_requested.emit(
                    self.infos[checked[0]].filepath
                )
            )
            menu.addAction(preview_action)

        menu.exec(self.table.viewport().mapToGlobal(pos))
