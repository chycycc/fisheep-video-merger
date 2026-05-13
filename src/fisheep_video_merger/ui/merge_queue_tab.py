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
    QHBoxLayout,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QAbstractItemView,
    QMenu,
    QLineEdit,
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

    # 信号：选中项改变时发射该项所对应的输出全路径，供侧栏详情展示 (U-3 联动)
    selection_path_changed = Signal(str)

    COL_CHECK = 0        # 选择框
    COL_STATUS = 1       # 状态图标
    COL_OUTPUT_NAME = 2  # 输出文件名
    COL_SOURCE = 3       # 关联源文件 (U-7 合二为一)

    HEADERS = ["", "状态", "输出文件名", "关联源文件"]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.tasks: list[MergeTask] = []
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
        self.search_edit.setPlaceholderText("🔍 搜索输出文件名或源文件...")
        self.search_edit.setClearButtonEnabled(True)
        self.search_edit.textChanged.connect(self._on_search)
        search_layout.addWidget(self.search_edit)
        layout.addLayout(search_layout)

        self.table = QTableWidget()
        self.table.setColumnCount(len(self.HEADERS))
        self.table.setHorizontalHeaderLabels(self.HEADERS)

        # 选择框列 — 窄且固定
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(self.COL_CHECK, QHeaderView.Fixed)
        self.table.setColumnWidth(self.COL_CHECK, 30)

        # 其他列拉伸模式 (S-6: 采用方案A 黄金比例 50:50 等比自适应伸缩，保证长字平摊)
        header.setSectionResizeMode(self.COL_STATUS, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(self.COL_OUTPUT_NAME, QHeaderView.Stretch)
        header.setSectionResizeMode(self.COL_SOURCE, QHeaderView.Stretch)

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

        # 选择事件联动 (U-3)
        self.table.itemSelectionChanged.connect(self._on_selection_changed)

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

            # 关联源文件 (U-7 & 强化: 智能提取去噪，提升视觉密度)
            import re
            v_name = os.path.basename(task.video_file)
            a_name = os.path.basename(task.audio_file)
            
            v_stem = os.path.splitext(v_name)[0]
            a_stem = os.path.splitext(a_name)[0]
            
            def clean_stem(s: str):
                # 💡 只修剪如 _2, _30280 等无用纯数字尾缀，不得切断大名核心 (如 _bilibili)
                return re.sub(r'(_[0-9]+|_[vaVA])$', '', s)
                
            v_clean = clean_stem(v_stem)
            a_clean = clean_stem(a_stem)
            
            if v_clean.lower() == a_clean.lower():
                # 孪生对匹配：用高密度整合呈现模式，字数减少 50%
                display_text = f"🎬🔊 {v_clean}"
            else:
                # 差异对匹配：平铺展示
                display_text = f"🎬 {v_name} | 🔊 {a_name}"

            source_item = QTableWidgetItem(display_text)
            source_item.setFlags(source_item.flags() & ~Qt.ItemIsEditable)
            source_item.setToolTip(f"🎬 视频: {task.video_file}\n🔊 音频: {task.audio_file}")
            self.table.setItem(i, self.COL_SOURCE, source_item)

        # 重新应用当前搜索过滤
        if hasattr(self, "search_edit") and self.search_edit.text():
            self._on_search(self.search_edit.text())

        self.table.blockSignals(False)

    def update_output_paths(self, paths_with_display: list[tuple[str, str]]):
        """缓存预计输出全路径并驱动联动展示 (U-3)"""
        self.calculated_output_paths = [x[0] for x in paths_with_display]
        # 刷新一下当前的选中详情
        self._on_selection_changed()

    def _on_selection_changed(self):
        """行选中事件联动回调：提取该行的计算全路径发射给主窗口"""
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            self.selection_path_changed.emit("")
            return

        # 仅以第一个选中的行为准进行详情投送
        idx = rows[0].row()
        if 0 <= idx < len(self.calculated_output_paths):
            self.selection_path_changed.emit(self.calculated_output_paths[idx])
        else:
            self.selection_path_changed.emit("")

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

    def _on_search(self, text: str):
        """过滤搜索"""
        text = text.strip().lower()
        for row in range(self.table.rowCount()):
            output_item = self.table.item(row, self.COL_OUTPUT_NAME)
            source_item = self.table.item(row, self.COL_SOURCE)

            match = False
            if not text:
                match = True
            else:
                if output_item and text in output_item.text().lower():
                    match = True
                elif source_item and (
                    text in source_item.text().lower() or 
                    text in (source_item.toolTip() or "").lower()
                ):
                    match = True

            self.table.setRowHidden(row, not match)
