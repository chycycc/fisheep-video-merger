"""
合并队列标签页
显示所有已确认的合并任务，支持复选框选择
复选框作为表格第一列（序号列之后），支持勾选/取消勾选
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
from PySide6.QtGui import QColor, QBrush, QAction

from fisheep_video_merger.core.matcher import MergeTask


class MergeQueueTab(QWidget):
    """合并队列标签页"""

    tasks_changed = Signal()
    preview_requested = Signal(str)
    batch_rename_requested = Signal(list)
    checked_state_changed = Signal()

    COL_CHECK = 0        # 选择框
    COL_STATUS = 1       # 状态图标
    COL_OUTPUT_NAME = 2  # 输出文件名
    COL_VIDEO = 3        # 源视频文件
    COL_AUDIO = 4        # 源音频文件
    COL_OUTPUT_PATH = 5  # 预计输出路径

    HEADERS = ["", "状态", "输出文件名", "源视频文件", "源音频文件", "预计输出路径"]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.tasks: list[MergeTask] = []
        self._setup_ui()

    def _setup_ui(self):
        """初始化界面"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.table = QTableWidget()
        self.table.setColumnCount(len(self.HEADERS))
        self.table.setHorizontalHeaderLabels(self.HEADERS)

        # 选择框列 — 窄且固定
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(self.COL_CHECK, QHeaderView.Fixed)
        self.table.setColumnWidth(self.COL_CHECK, 30)

        # 其他列拉伸模式
        header.setSectionResizeMode(self.COL_STATUS, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(self.COL_OUTPUT_NAME, QHeaderView.Interactive)
        header.setSectionResizeMode(self.COL_VIDEO, QHeaderView.Interactive)
        header.setSectionResizeMode(self.COL_AUDIO, QHeaderView.Interactive)
        header.setSectionResizeMode(self.COL_OUTPUT_PATH, QHeaderView.Interactive)

        # 设置默认列宽
        self.table.setColumnWidth(self.COL_OUTPUT_NAME, 120)
        self.table.setColumnWidth(self.COL_VIDEO, 200)
        self.table.setColumnWidth(self.COL_AUDIO, 200)
        self.table.setColumnWidth(self.COL_OUTPUT_PATH, 200)

        header.setStretchLastSection(False)

        # 行高与选择
        self.table.verticalHeader().setDefaultSectionSize(24)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.table.setAlternatingRowColors(True)

        # 编辑事件
        self.table.itemChanged.connect(self._on_item_changed)

        # 右键菜单
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._show_context_menu)

        layout.addWidget(self.table)

    def set_tasks(self, tasks: list[MergeTask]):
        """设置任务列表"""
        self.tasks = tasks
        self._refresh_table()

    def get_tasks(self) -> list[MergeTask]:
        """获取任务列表"""
        return self.tasks

    def add_task(self, task: MergeTask):
        """添加单个任务"""
        self.tasks.append(task)
        self._refresh_table()
        self.tasks_changed.emit()

    def remove_selected_tasks(self):
        """移除选中的任务"""
        rows = sorted(set(
            idx.row() for idx in self.table.selectedIndexes()
        ), reverse=True)
        for row in rows:
            if row < len(self.tasks):
                del self.tasks[row]
        self._refresh_table()
        self.tasks_changed.emit()

    def remove_task_by_index(self, index: int):
        """按索引移除任务"""
        if 0 <= index < len(self.tasks):
            del self.tasks[index]
            self._refresh_table()
            self.tasks_changed.emit()

    def clear_tasks(self):
        """清空所有任务"""
        self.tasks.clear()
        self._refresh_table()
        self.tasks_changed.emit()

    def update_task_status(self, index: int, success: bool, error_msg: Optional[str] = None):
        """更新单个任务状态（增量更新，不重建整个表格）"""
        if 0 <= index < len(self.tasks):
            task = self.tasks[index]
            task.status = "success" if success else "error"
            task.error_message = error_msg
            self._update_row(index)

    def _update_row(self, row: int):
        """增量更新指定行的显示"""
        if row >= len(self.tasks) or row >= self.table.rowCount():
            return
        task = self.tasks[row]
        self.table.blockSignals(True)

        # 选择框列
        check_item = self.table.item(row, self.COL_CHECK)
        if check_item:
            if task.status == "pending":
                check_item.setCheckState(Qt.Checked)
            else:
                check_item.setCheckState(Qt.Unchecked)

        # 状态
        status_text = "✅" if task.status == "success" else (
            "❌" if task.status == "error" else "⏳"
        )
        status_item = self.table.item(row, self.COL_STATUS)
        if status_item:
            status_item.setText(status_text)
            if task.status == "error":
                status_item.setToolTip(task.error_message or "未知错误")

        self.table.blockSignals(False)

    def _refresh_table(self):
        """刷新表格显示"""
        self.table.blockSignals(True)
        self.table.setRowCount(len(self.tasks))

        for i, task in enumerate(self.tasks):
            # 选择框列
            check_item = QTableWidgetItem("")
            check_item.setFlags(
                Qt.ItemIsUserCheckable | Qt.ItemIsEnabled | Qt.ItemIsSelectable
            )
            # pending 任务默认勾选
            if task.status == "pending":
                check_item.setCheckState(Qt.Checked)
            else:
                check_item.setCheckState(Qt.Unchecked)
            check_item.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(i, self.COL_CHECK, check_item)

            # 状态
            status_text = "✅" if task.status == "success" else (
                "❌" if task.status == "error" else "⏳"
            )
            status_item = QTableWidgetItem(status_text)
            status_item.setTextAlignment(Qt.AlignCenter)
            status_item.setFlags(status_item.flags() & ~Qt.ItemIsEditable)
            if task.status == "error":
                status_item.setToolTip(task.error_message or "未知错误")
            self.table.setItem(i, self.COL_STATUS, status_item)

            # 输出文件名
            name_item = QTableWidgetItem(task.output_name)
            name_item.setFlags(name_item.flags() | Qt.ItemIsEditable)
            if task.is_multi_episode:
                name_item.setBackground(QBrush(QColor(255, 255, 200)))
                name_item.setToolTip("疑似多集，请确认名称")
            self.table.setItem(i, self.COL_OUTPUT_NAME, name_item)

            # 源视频文件
            video_item = QTableWidgetItem(task.video_file)
            video_item.setFlags(video_item.flags() & ~Qt.ItemIsEditable)
            video_item.setToolTip(task.video_file)
            self.table.setItem(i, self.COL_VIDEO, video_item)

            # 源音频文件
            audio_item = QTableWidgetItem(task.audio_file)
            audio_item.setFlags(audio_item.flags() & ~Qt.ItemIsEditable)
            audio_item.setToolTip(task.audio_file)
            self.table.setItem(i, self.COL_AUDIO, audio_item)

            # 预计输出路径
            path_item = QTableWidgetItem("")
            path_item.setFlags(path_item.flags() & ~Qt.ItemIsEditable)
            self.table.setItem(i, self.COL_OUTPUT_PATH, path_item)

        self.table.blockSignals(False)

    def update_output_paths(self, paths: list[str]):
        """更新预计输出路径列"""
        self.table.blockSignals(True)
        for i, path in enumerate(paths):
            if i < self.table.rowCount():
                item = self.table.item(i, self.COL_OUTPUT_PATH)
                if item:
                    item.setText(path)
                    item.setToolTip(path)
        self.table.blockSignals(False)

    def _on_item_changed(self, item: QTableWidgetItem):
        """单元格内容变更处理"""
        row = item.row()
        if row >= len(self.tasks):
            return

        col = item.column()
        if col == self.COL_OUTPUT_NAME:
            self.tasks[row].output_name = item.text()
            self.tasks_changed.emit()
        elif col == self.COL_CHECK:
            self.checked_state_changed.emit()

    def _show_context_menu(self, pos):
        """显示右键菜单"""
        selected_rows = set(
            idx.row() for idx in self.table.selectedIndexes()
        )
        if not selected_rows:
            return

        menu = QMenu(self)

        # 勾选/取消勾选
        any_checked = any(
            self._is_row_checked(r) for r in selected_rows
        )
        if any_checked:
            uncheck_action = QAction("取消勾选选中任务", self)
            uncheck_action.triggered.connect(
                lambda: self._toggle_checked(selected_rows, False)
            )
            menu.addAction(uncheck_action)
        else:
            check_action = QAction("勾选选中任务", self)
            check_action.triggered.connect(
                lambda: self._toggle_checked(selected_rows, True)
            )
            menu.addAction(check_action)

        # 批量命名
        if len(selected_rows) > 1:
            batch_action = QAction("批量命名...", self)
            batch_action.triggered.connect(
                lambda: self.batch_rename_requested.emit(list(selected_rows))
            )
            menu.addAction(batch_action)

        # 移除任务
        remove_action = QAction("移除任务", self)
        remove_action.triggered.connect(self.remove_selected_tasks)
        menu.addAction(remove_action)

        menu.addSeparator()

        # 预览
        if len(selected_rows) == 1:
            row = list(selected_rows)[0]
            if row < len(self.tasks):
                task = self.tasks[row]

                preview_video = QAction("预览视频", self)
                preview_video.triggered.connect(
                    lambda: self.preview_requested.emit(task.video_file)
                )
                menu.addAction(preview_video)

                preview_audio = QAction("预览音频", self)
                preview_audio.triggered.connect(
                    lambda: self.preview_requested.emit(task.audio_file)
                )
                menu.addAction(preview_audio)

        menu.exec(self.table.viewport().mapToGlobal(pos))

    def _is_row_checked(self, row: int) -> bool:
        """检查指定行是否勾选"""
        item = self.table.item(row, self.COL_CHECK)
        if item is None:
            return False
        return item.checkState() == Qt.Checked

    def _toggle_checked(self, rows: set[int], checked: bool):
        """切换指定行的勾选状态"""
        self.table.blockSignals(True)
        state = Qt.Checked if checked else Qt.Unchecked
        for row in rows:
            item = self.table.item(row, self.COL_CHECK)
            if item:
                item.setCheckState(state)
        self.table.blockSignals(False)
        self.checked_state_changed.emit()

    def get_selected_rows(self) -> list[int]:
        """获取选中行索引列表"""
        return sorted(set(
            idx.row() for idx in self.table.selectedIndexes()
        ))

    def get_checked_indices(self) -> list[int]:
        """获取所有已勾选的行索引"""
        result = []
        for i in range(self.table.rowCount()):
            item = self.table.item(i, self.COL_CHECK)
            if item and item.checkState() == Qt.Checked:
                result.append(i)
        return result

    def get_checked_tasks(self) -> list[MergeTask]:
        """获取所有已勾选的任务"""
        indices = self.get_checked_indices()
        return [self.tasks[i] for i in indices if i < len(self.tasks)]

    def get_checked_task_count(self) -> int:
        """获取已勾选的任务数量"""
        return len(self.get_checked_indices())

    def get_task_count(self) -> int:
        """获取任务数量"""
        return len(self.tasks)

    def has_tasks(self) -> bool:
        """是否有任务"""
        return len(self.tasks) > 0
