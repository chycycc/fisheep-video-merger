"""
待整理标签页
显示未配对的零散视频和音频文件
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
from PySide6.QtGui import QAction, QBrush, QColor

from fisheep_video_merger.utils.ffprobe import StreamInfo, StreamType


class PendingTab(QWidget):
    """待整理标签页"""

    # 信号：请求配对选中的文件
    pair_requested = Signal(StreamInfo, StreamInfo)
    # 信号：请求预览文件
    preview_requested = Signal(str)
    # 信号：标记文件为已完整
    mark_complete_requested = Signal(StreamInfo)
    # 信号：请求移除文件
    remove_requested = Signal(list)  # list[StreamInfo]

    COL_TYPE = 0     # 类型图标
    COL_FILENAME = 1  # 文件名
    COL_FOLDER = 2    # 所在文件夹
    COL_SIZE = 3      # 文件大小

    HEADERS = ["类型", "文件名", "所在文件夹", "大小"]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.video_files: list[StreamInfo] = []
        self.audio_files: list[StreamInfo] = []
        self._setup_ui()

    def _setup_ui(self):
        """初始化界面"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # 搜索栏
        search_layout = QHBoxLayout()
        search_layout.setContentsMargins(4, 4, 4, 4)
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("🔍 搜索文件名或文件夹...")
        self.search_edit.setClearButtonEnabled(True)
        self.search_edit.textChanged.connect(self._on_search)
        search_layout.addWidget(self.search_edit)
        layout.addLayout(search_layout)

        self.table = QTableWidget()
        self.table.setColumnCount(len(self.HEADERS))
        self.table.setHorizontalHeaderLabels(self.HEADERS)

        # 表头拉伸模式
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(self.COL_TYPE, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(self.COL_FILENAME, QHeaderView.Interactive)
        header.setSectionResizeMode(self.COL_FOLDER, QHeaderView.Stretch)
        header.setSectionResizeMode(self.COL_SIZE, QHeaderView.Fixed)
        self.table.setColumnWidth(self.COL_FILENAME, 350)
        self.table.setColumnWidth(self.COL_SIZE, 80)

        # 选择模式
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.table.setAlternatingRowColors(True)

        # 禁止编辑
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)

        # 右键菜单
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._show_context_menu)

        layout.addWidget(self.table)

    def set_files(self, videos: list[StreamInfo], audios: list[StreamInfo]):
        """设置文件列表"""
        self.video_files = list(videos)
        self.audio_files = list(audios)
        self._refresh_table()

    def clear(self):
        """清空列表"""
        self.video_files.clear()
        self.audio_files.clear()
        self._refresh_table()

    def _refresh_table(self):
        """刷新表格显示"""
        self.table.setRowCount(0)

        all_files = []
        for v in self.video_files:
            all_files.append((StreamType.VIDEO_ONLY, v))
        for a in self.audio_files:
            all_files.append((StreamType.AUDIO_ONLY, a))

        # 按所在目录分组显示
        all_files.sort(key=lambda x: (os.path.dirname(x[1].filepath), x[0].value))

        self.table.setRowCount(len(all_files))

        # 统计目录文件配对状况以便推荐
        from collections import defaultdict
        dir_counts = defaultdict(lambda: {"video": 0, "audio": 0})
        for st, info in all_files:
            d = os.path.dirname(info.filepath)
            if st == StreamType.VIDEO_ONLY:
                dir_counts[d]["video"] += 1
            elif st == StreamType.AUDIO_ONLY:
                dir_counts[d]["audio"] += 1

        for i, (stream_type, info) in enumerate(all_files):
            f_dir = os.path.dirname(info.filepath)
            recommended = (
                dir_counts[f_dir]["video"] == 1 and
                dir_counts[f_dir]["audio"] == 1
            )
            bg = QBrush(QColor(235, 255, 235)) if recommended else None

            # 类型图标
            icon = "🎬" if stream_type == StreamType.VIDEO_ONLY else "🔊"
            type_item = QTableWidgetItem(icon)
            type_item.setTextAlignment(Qt.AlignCenter)
            if bg:
                type_item.setBackground(bg)
                type_item.setToolTip("💡 推荐配对：同文件夹内唯一的音视频组合")
            self.table.setItem(i, self.COL_TYPE, type_item)

            # 文件名
            name_item = QTableWidgetItem(os.path.basename(info.filepath))
            name_item.setToolTip(info.filepath)
            if bg:
                name_item.setBackground(bg)
            self.table.setItem(i, self.COL_FILENAME, name_item)

            # 所在文件夹
            folder = os.path.dirname(info.filepath)
            folder_item = QTableWidgetItem(folder)
            folder_item.setToolTip(folder)
            if bg:
                folder_item.setBackground(bg)
            self.table.setItem(i, self.COL_FOLDER, folder_item)

            # 文件大小
            try:
                size_bytes = os.path.getsize(info.filepath)
                if size_bytes >= 1024 * 1024:
                    size_text = f"{size_bytes / (1024 * 1024):.1f} MB"
                elif size_bytes >= 1024:
                    size_text = f"{size_bytes / 1024:.0f} KB"
                else:
                    size_text = f"{size_bytes} B"
            except OSError:
                size_text = "—"
            size_item = QTableWidgetItem(size_text)
            size_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            size_item.setFlags(size_item.flags() & ~Qt.ItemIsEditable)
            if bg:
                size_item.setBackground(bg)
            self.table.setItem(i, self.COL_SIZE, size_item)

            # 存储原始数据用于检索
            type_item.setData(Qt.UserRole, info.filepath)
            type_item.setData(Qt.UserRole + 1, stream_type.value)

        # 重新应用当前搜索过滤
        if hasattr(self, "search_edit") and self.search_edit.text():
            self._on_search(self.search_edit.text())

    def get_selected_infos(self) -> list[StreamInfo]:
        """获取选中的文件信息列表"""
        rows = sorted(set(
            idx.row() for idx in self.table.selectedIndexes()
        ))

        infos: list[StreamInfo] = []
        for row in rows:
            type_item = self.table.item(row, self.COL_TYPE)
            if type_item is None:
                continue
            filepath = type_item.data(Qt.UserRole)
            stream_type_str = type_item.data(Qt.UserRole + 1)

            # 从列表中查找对应的 StreamInfo
            all_infos = self.video_files + self.audio_files
            for info in all_infos:
                if info.filepath == filepath:
                    infos.append(info)
                    break

        return infos

    def has_items(self) -> bool:
        """是否有待整理文件"""
        return len(self.video_files) > 0 or len(self.audio_files) > 0

    def _show_context_menu(self, pos):
        """显示右键菜单"""
        selected = self.get_selected_infos()
        if not selected:
            return

        menu = QMenu(self)

        # 配对所选
        videos = [s for s in selected if s.stream_type == StreamType.VIDEO_ONLY]
        audios = [s for s in selected if s.stream_type == StreamType.AUDIO_ONLY]

        if len(videos) == 1 and len(audios) == 1 and len(selected) == 2:
            pair_action = QAction("配对所选", self)
            pair_action.triggered.connect(
                lambda: self.pair_requested.emit(videos[0], audios[0])
            )
            menu.addAction(pair_action)

        menu.addSeparator()

        # 移除所选
        remove_action = QAction("🗑 移除所选", self)
        remove_action.triggered.connect(
            lambda: self.remove_requested.emit(selected)
        )
        menu.addAction(remove_action)

        # 预览
        if len(selected) == 1:
            preview_action = QAction("预览", self)
            preview_action.triggered.connect(
                lambda: self.preview_requested.emit(selected[0].filepath)
            )
            menu.addAction(preview_action)

            # 标记为已完整
            mark_action = QAction("标记为\"已完整\"跳过", self)
            mark_action.triggered.connect(
                lambda: self.mark_complete_requested.emit(selected[0])
            )
            menu.addAction(mark_action)

        menu.exec(self.table.viewport().mapToGlobal(pos))

    def _on_search(self, text: str):
        """过滤搜索"""
        text = text.strip().lower()
        for row in range(self.table.rowCount()):
            filename_item = self.table.item(row, self.COL_FILENAME)
            folder_item = self.table.item(row, self.COL_FOLDER)

            match = False
            if not text:
                match = True
            else:
                if filename_item and text in filename_item.text().lower():
                    match = True
                elif folder_item and text in folder_item.text().lower():
                    match = True

            self.table.setRowHidden(row, not match)
