"""
muxed 文件标签页
显示已包含音视频的完整 m4s 文件，支持转封装操作
"""

import os
from typing import Optional

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QAbstractItemView,
    QMenu,
    QLineEdit,
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QAction

from fisheep_video_merger.utils.ffprobe import StreamInfo


class MuxedTab(QWidget):
    """已完整文件标签页"""

    preview_requested = Signal(str)  # 请求预览
    remux_requested = Signal(list)   # 请求转封装选中文件
    tasks_changed = Signal()

    # 信号：选中项改变时发射当前对应的绝对全路径 (U-3 联动)
    selection_path_changed = Signal(str)

    COL_CHECK = 0      # 选择框
    COL_STATUS = 1     # 状态
    COL_FILENAME = 2   # 文件名
    COL_CODECS = 3     # 编码格式

    HEADERS = ["", "状态", "文件名", "编码"]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.infos: list[StreamInfo] = []
        self.statuses: dict[str, str] = {}  # filepath -> "pending"/"success"/"error"
        self.calculated_output_paths: list[str] = []
        self._setup_ui()

    def _setup_ui(self):
        """初始化界面"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # 搜索栏
        search_layout = QHBoxLayout()
        search_layout.setContentsMargins(4, 4, 4, 4)
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("🔍 搜索已完整文件名...")
        self.search_edit.setClearButtonEnabled(True)
        self.search_edit.textChanged.connect(self._on_search)
        search_layout.addWidget(self.search_edit)
        layout.addLayout(search_layout)

        self.table = QTableWidget()
        self.table.setColumnCount(len(self.HEADERS))
        self.table.setHorizontalHeaderLabels(self.HEADERS)

        header = self.table.horizontalHeader()
        header.setSectionResizeMode(self.COL_CHECK, QHeaderView.Fixed)
        self.table.setColumnWidth(self.COL_CHECK, 30)
        header.setSectionResizeMode(self.COL_STATUS, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(self.COL_FILENAME, QHeaderView.Interactive)
        header.setSectionResizeMode(self.COL_CODECS, QHeaderView.Interactive)

        # 设置合理的初始缺省列宽
        self.table.setColumnWidth(self.COL_FILENAME, 300)
        self.table.setColumnWidth(self.COL_CODECS, 150)

        header.setStretchLastSection(True)

        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        
        # 选中联动 (U-3)
        self.table.itemSelectionChanged.connect(self._on_selection_changed)
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

            # 状态 (U-1: 改用 📄 文档图标消除和复选框的撞脸歧义)
            status_text = {"pending": "📄", "success": "✅", "error": "❌"}.get(
                status, "📄"
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

        # 重新应用当前搜索过滤
        if hasattr(self, "search_edit") and self.search_edit.text():
            self._on_search(self.search_edit.text())

        self.table.blockSignals(False)

    def update_output_paths(self, paths_with_display: list[tuple[str, str]]):
        """缓存预计输出绝对全路径并激活侧栏联动 (U-3)"""
        self.calculated_output_paths = [x[0] for x in paths_with_display]
        self._on_selection_changed()

    def _on_selection_changed(self):
        """选中项联动响应：提取第一行文件路径供侧栏"""
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            self.selection_path_changed.emit("")
            return
            
        idx = rows[0].row()
        if 0 <= idx < len(self.calculated_output_paths):
            self.selection_path_changed.emit(self.calculated_output_paths[idx])
        else:
            self.selection_path_changed.emit("")

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

    def _on_search(self, text: str):
        """过滤搜索"""
        text = text.strip().lower()
        for row in range(self.table.rowCount()):
            filename_item = self.table.item(row, self.COL_FILENAME)
            
            match = False
            if not text:
                match = True
            else:
                if filename_item and text in filename_item.text().lower():
                    match = True

            self.table.setRowHidden(row, not match)
