"""
主窗口模块
整合所有 UI 组件和交互逻辑
"""

import os
import threading
from typing import Optional

from PySide6.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QSplitter,
    QPushButton,
    QLabel,
    QTabWidget,
    QFileDialog,
    QProgressBar,
    QStatusBar,
    QMessageBox,
    QApplication,
)
from PySide6.QtCore import Qt, Signal, QObject, Slot
from PySide6.QtGui import QDragEnterEvent, QDropEvent, QShortcut, QKeySequence

from fisheep_video_merger.core.matcher import (
    MergeTask,
    MatchResult,
    auto_match,
    create_manual_task,
)
from fisheep_video_merger.core.scanner import scan_multiple_directories
from fisheep_video_merger.core.path_utils import (
    generate_output_path,
)
from fisheep_video_merger.core.merger import (
    merge_single,
    remux_single,
    ConflictStrategy,
    MergeResult,
)
from fisheep_video_merger.ui.merge_queue_tab import MergeQueueTab
from fisheep_video_merger.ui.pending_tab import PendingTab
from fisheep_video_merger.ui.muxed_tab import MuxedTab
from fisheep_video_merger.ui.settings_panel import SettingsPanel
from fisheep_video_merger.ui.dialogs import (
    BatchRenameDialog,
    ConflictDialog,
    DeleteConfirmDialog,
    ResultSummaryDialog,
    NameInputDialog,
)
from fisheep_video_merger.utils.ffprobe import StreamInfo, StreamType, check_ffmpeg_available
from fisheep_video_merger.utils.logger import get_logger, setup_logger

logger = get_logger()


class ScanSignals(QObject):
    """扫描线程信号"""
    progress = Signal(int, int)  # 已完成数, 总数
    finished = Signal(object)    # StreamInfo 列表
    error = Signal(str)


class MergeSignals(QObject):
    """合并线程信号"""
    progress = Signal(int, int, str)  # 当前序号, 总数, 状态文本
    task_status = Signal(int, bool, object)  # 索引, 成功标志, 错误信息
    finished = Signal(list)  # MergeResult 列表
    conflict_requested = Signal(str)  # 请求显示重名冲突对话框


class MainWindow(QMainWindow):
    """主窗口"""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("B站m4s合并工具")
        self.resize(1100, 700)

        # 数据
        self.root_paths: list[str] = []
        self.all_stream_infos: list[StreamInfo] = []
        self.muxed_files: list[StreamInfo] = []
        self.is_merging = False

        # 检查 ffmpeg
        self.ffmpeg_available = check_ffmpeg_available()
        if not self.ffmpeg_available:
            logger.warning("ffmpeg/ffprobe 不可用")

        # 初始化 UI
        self._setup_ui()

        # 设置接受拖拽
        self.setAcceptDrops(True)

        # 更新状态
        self._update_status()

    def _setup_ui(self):
        """初始化主界面"""
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(6, 6, 6, 6)
        main_layout.setSpacing(4)

        # === 顶部工具栏 ===
        toolbar_layout = QHBoxLayout()
        toolbar_layout.setContentsMargins(0, 0, 0, 0)

        self.add_folder_btn = QPushButton("📂 添加文件夹")
        self.add_folder_btn.clicked.connect(self._on_add_folder)
        toolbar_layout.addWidget(self.add_folder_btn)

        self.add_files_btn = QPushButton("📄 添加文件")
        self.add_files_btn.clicked.connect(self._on_add_files)
        toolbar_layout.addWidget(self.add_files_btn)

        self.pair_btn = QPushButton("🔗 配对所选")
        self.pair_btn.setEnabled(False)
        self.pair_btn.clicked.connect(self._on_pair_btn)
        toolbar_layout.addWidget(self.pair_btn)

        self.clear_btn = QPushButton("🧹 清空列表")
        self.clear_btn.clicked.connect(self._on_clear)
        toolbar_layout.addWidget(self.clear_btn)

        toolbar_layout.addStretch()

        self.status_text = QLabel("就绪")
        self.status_text.setStyleSheet("color: gray;")
        toolbar_layout.addWidget(self.status_text)

        main_layout.addLayout(toolbar_layout)

        # === 主区域（左右分栏） ===
        splitter = QSplitter(Qt.Horizontal)

        # 左侧：标签页
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)

        self.tab_widget = QTabWidget()
        self.merge_queue_tab = MergeQueueTab()
        self.pending_tab = PendingTab()
        self.muxed_tab = MuxedTab()

        self.tab_widget.addTab(self.merge_queue_tab, "合并队列")
        self.tab_widget.addTab(self.pending_tab, "待整理")
        self.tab_widget.addTab(self.muxed_tab, "已完整")

        left_layout.addWidget(self.tab_widget)
        splitter.addWidget(left_widget)

        # 右侧：设置面板
        self.settings_panel = SettingsPanel()
        splitter.addWidget(self.settings_panel)

        # 设置比例（65% : 35%）
        splitter.setStretchFactor(0, 65)
        splitter.setStretchFactor(1, 35)
        splitter.setSizes([715, 385])

        main_layout.addWidget(splitter, 1)

        # === 底部进度条 ===
        bottom_widget = QWidget()
        bottom_widget.setStyleSheet("background-color: transparent;")
        bottom_layout = QHBoxLayout(bottom_widget)
        bottom_layout.setContentsMargins(0, 2, 0, 0)
        bottom_layout.setSpacing(4)

        self.progress_bar = QProgressBar()
        self.progress_bar.setMinimum(0)
        self.progress_bar.setMaximum(100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setFormat("")
        self.progress_bar.setFixedHeight(18)
        self.progress_bar.setStyleSheet(
            "QProgressBar { border: none; border-radius: 3px; "
            "background-color: #e0e0e0; text-align: center; font-size: 11px; }"
            "QProgressBar::chunk { background-color: #4CAF50; border-radius: 3px; }"
        )
        bottom_layout.addWidget(self.progress_bar, 1)

        self.task_status_label = QLabel("")
        self.task_status_label.setMinimumWidth(200)
        self.task_status_label.setAlignment(
            Qt.AlignRight | Qt.AlignVCenter
        )
        self.task_status_label.setStyleSheet("color: #666; font-size: 12px;")
        bottom_layout.addWidget(self.task_status_label)

        main_layout.addWidget(bottom_widget)

        # === 连接信号 ===
        self._connect_signals()

        # === 快捷键 ===
        QShortcut(QKeySequence("Ctrl+O"), self, self._on_add_folder)
        QShortcut(QKeySequence("Ctrl+P"), self, self._on_pair_btn)
        QShortcut(QKeySequence(Qt.Key_Delete), self,
                  lambda: self.merge_queue_tab.remove_selected_tasks())
        QShortcut(QKeySequence("Ctrl+Return"), self, self._on_start_merge)

    def _connect_signals(self):
        """连接信号"""
        # 设置面板
        self.settings_panel.start_merge_clicked.connect(self._on_start_merge)
        self.settings_panel.settings_changed.connect(self._update_status)
        self.settings_panel.settings_changed.connect(self._update_all_output_paths)

        # 待整理标签页
        self.pending_tab.pair_requested.connect(self._on_pair_requested)
        self.pending_tab.preview_requested.connect(self._on_preview)
        self.pending_tab.mark_complete_requested.connect(self._on_mark_complete)
        self.pending_tab.remove_requested.connect(self._on_pending_remove)

        # 合并队列标签页
        self.merge_queue_tab.preview_requested.connect(self._on_preview)
        self.merge_queue_tab.tasks_changed.connect(self._update_status)
        self.merge_queue_tab.batch_rename_requested.connect(self._on_batch_rename)
        self.merge_queue_tab.checked_state_changed.connect(self._update_status)

        # muxed 标签页
        self.muxed_tab.preview_requested.connect(self._on_preview)
        self.muxed_tab.remux_requested.connect(self._on_remux_requested)
        self.muxed_tab.tasks_changed.connect(self._update_status)

    def _update_status(self):
        """更新界面状态"""
        task_count = self.merge_queue_tab.get_task_count()
        checked_count = self.merge_queue_tab.get_checked_task_count()
        pending_count = (
            len(self.pending_tab.video_files) +
            len(self.pending_tab.audio_files)
        )
        muxed_count = self.muxed_tab.get_file_count()
        output_dir = self.settings_panel.get_output_dir()

        # 更新状态文本
        parts = []
        if task_count > 0:
            parts.append(f"队列: {checked_count}/{task_count}")
        if pending_count > 0:
            parts.append(f"待整理: {pending_count} 个文件")
        if muxed_count > 0:
            parts.append(f"已完整: {muxed_count} 个")
        if not parts:
            parts.append("就绪")

        self.status_text.setText(" | ".join(parts))

        # 配对按钮状态
        selected = self.pending_tab.get_selected_infos()
        videos = [s for s in selected if s.stream_type == StreamType.VIDEO_ONLY]
        audios = [s for s in selected if s.stream_type == StreamType.AUDIO_ONLY]
        can_pair = (
            len(videos) == 1 and len(audios) == 1
            and len(selected) == 2
            and not self.is_merging
        )
        self.pair_btn.setEnabled(can_pair)

        # 更新开始合并按钮状态
        can_merge = (
            checked_count > 0
            and bool(output_dir)
            and self.ffmpeg_available
            and not self.is_merging
        )
        self.settings_panel.set_start_enabled(can_merge)

        if not self.ffmpeg_available:
            self.settings_panel.set_status("⚠️ ffmpeg 不可用，请安装并加入 PATH", True)
        elif not output_dir:
            self.settings_panel.set_status("请设置输出目录")
        elif task_count == 0:
            self.settings_panel.set_status("请先添加文件夹并完成配对")
        elif checked_count == 0:
            self.settings_panel.set_status("请勾选要合并的任务")
        else:
            self.settings_panel.set_status(f"准备就绪，已勾选 {checked_count}/{task_count} 个任务")

        # 更新表格输出路径
        self._update_all_output_paths()

    def _on_add_folder(self):
        """添加文件夹按钮点击"""
        directory = QFileDialog.getExistingDirectory(
            self, "选择包含 m4s 文件的文件夹",
            os.path.expanduser("~"),
        )
        if directory:
            self._add_folder(directory)

    def _on_add_files(self):
        """添加单个 m4s 文件按钮点击"""
        files, _ = QFileDialog.getOpenFileNames(
            self, "选择 m4s 文件",
            os.path.expanduser("~"),
            "m4s 文件 (*.m4s);;所有文件 (*)",
        )
        if files:
            self._add_files(files)

    def _add_files(self, filepaths: list[str]):
        """添加单个文件并分析流类型"""
        from fisheep_video_merger.utils.ffprobe import analyze_file, StreamType

        self.status_text.setText("正在分析文件...")
        self.add_folder_btn.setEnabled(False)
        self.add_files_btn.setEnabled(False)

        new_videos, new_audios, new_muxed = [], [], []

        for fp in filepaths:
            if not fp.lower().endswith(".m4s"):
                continue
            info = analyze_file(fp)
            self.all_stream_infos.append(info)
            if info.stream_type == StreamType.VIDEO_ONLY:
                new_videos.append(info)
            elif info.stream_type == StreamType.AUDIO_ONLY:
                new_audios.append(info)
            elif info.stream_type == StreamType.MUXED:
                new_muxed.append(info)

        if new_videos or new_audios:
            self.pending_tab.video_files.extend(new_videos)
            self.pending_tab.audio_files.extend(new_audios)
            self.pending_tab._refresh_table()

        if new_muxed:
            self.muxed_files.extend(new_muxed)
            self.muxed_tab.set_files(self.muxed_files)

        self.add_folder_btn.setEnabled(True)
        self.add_files_btn.setEnabled(True)
        self.clear_btn.setEnabled(True)

        # 自动填充输出目录
        self._auto_set_output_dir()

        self._update_status()

        total = len(new_videos) + len(new_audios) + len(new_muxed)
        if total > 0:
            self.status_text.setText(
                f"已添加 {total} 个文件 "
                f"(视频:{len(new_videos)} 音频:{len(new_audios)} 完整:{len(new_muxed)})"
            )

    def _on_pair_btn(self):
        """配对按钮点击"""
        selected = self.pending_tab.get_selected_infos()
        videos = [s for s in selected if s.stream_type == StreamType.VIDEO_ONLY]
        audios = [s for s in selected if s.stream_type == StreamType.AUDIO_ONLY]
        if len(videos) == 1 and len(audios) == 1 and len(selected) == 2:
            self._on_pair_requested(videos[0], audios[0])

    def _add_folder(self, directory: str):
        """添加文件夹并开始扫描"""
        if directory in self.root_paths:
            QMessageBox.information(self, "提示", "该文件夹已在列表中")
            return

        self.root_paths.append(directory)
        self.status_text.setText("正在扫描...")
        self.add_folder_btn.setEnabled(False)
        self.clear_btn.setEnabled(False)

        # 启动扫描线程
        self._start_scan()

    def _start_scan(self):
        """启动扫描线程"""
        signals = ScanSignals()
        signals.progress.connect(self._on_scan_progress)
        signals.finished.connect(self._on_scan_finished)
        signals.error.connect(self._on_scan_error)

        def scan_worker():
            try:
                results = scan_multiple_directories(
                    self.root_paths,
                    progress_callback=lambda c, t: signals.progress.emit(c, t),
                )
                signals.finished.emit(results)
            except Exception as e:
                signals.error.emit(str(e))

        thread = threading.Thread(target=scan_worker, daemon=True)
        thread.start()

    @Slot(int, int)
    def _on_scan_progress(self, completed: int, total: int):
        """扫描进度更新"""
        self.status_text.setText(f"正在扫描... ({completed}/{total})")

    @Slot(object)
    def _on_scan_finished(self, results: list[StreamInfo]):
        """扫描完成"""
        self.all_stream_infos = results

        # 执行自动配对
        match_result = auto_match(results, self.root_paths)

        # 更新界面
        self.merge_queue_tab.set_tasks(match_result.auto_tasks)
        self.pending_tab.set_files(
            match_result.pending_videos,
            match_result.pending_audios,
        )
        self.muxed_files = match_result.muxed_files
        self.muxed_tab.set_files(match_result.muxed_files)

        # 自动填充输出目录
        self._auto_set_output_dir()

        # 更新输出路径
        self._update_all_output_paths()

        self.add_folder_btn.setEnabled(True)
        self.clear_btn.setEnabled(True)
        self._update_status()

        # 提示信息
        total = len(results)
        auto_count = len(match_result.auto_tasks)
        pending_v = len(match_result.pending_videos)
        pending_a = len(match_result.pending_audios)
        muxed_count = len(match_result.muxed_files)

        msg = (
            f"扫描完成！共 {total} 个文件\n"
            f"自动配对: {auto_count} 个任务\n"
            f"待整理: {pending_v} 视频 + {pending_a} 音频\n"
            f"已完整(跳过): {muxed_count} 个"
        )
        QMessageBox.information(self, "扫描完成", msg)

    @Slot(str)
    def _on_scan_error(self, error_msg: str):
        """扫描出错"""
        self.add_folder_btn.setEnabled(True)
        self.clear_btn.setEnabled(True)
        self.status_text.setText("扫描出错")
        QMessageBox.critical(self, "扫描错误", f"扫描过程中发生错误:\n{error_msg}")

    def _on_clear(self):
        """清空列表"""
        if self.is_merging:
            QMessageBox.warning(self, "提示", "合并进行中，无法清空列表")
            return

        reply = QMessageBox.question(
            self, "确认清空",
            "确定要清空所有扫描结果吗？",
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            self.root_paths.clear()
            self.all_stream_infos.clear()
            self.muxed_files.clear()
            self.merge_queue_tab.clear_tasks()
            self.pending_tab.clear()
            self.muxed_tab.clear()
            self.progress_bar.setValue(0)
            self.progress_bar.setFormat("")
            self.task_status_label.setText("")
            self._update_status()

    def _on_pair_requested(self, video_info: StreamInfo, audio_info: StreamInfo):
        """手动配对请求"""
        # 自动用文件所在文件夹的名称作为默认输出文件名
        source_dir = os.path.dirname(video_info.filepath)
        default_name = os.path.basename(source_dir) if source_dir else ""

        dialog = NameInputDialog(
            os.path.basename(video_info.filepath),
            os.path.basename(audio_info.filepath),
            source_dir,
            default_name,
            self,
        )
        if dialog.exec() == NameInputDialog.Accepted:
            name = dialog.get_name()
            if not name:
                QMessageBox.warning(self, "提示", "文件名不能为空")
                return

            # 找到所属根路径
            root_path = self._find_root(video_info.filepath)

            task = create_manual_task(video_info, audio_info, name, root_path)
            self.merge_queue_tab.add_task(task)

            # 从待整理中移除
            self._remove_from_pending(video_info)
            self._remove_from_pending(audio_info)

            # 更新输出路径
            self._update_all_output_paths()
            self._update_status()

    def _remove_from_pending(self, info: StreamInfo):
        """从待整理列表中移除文件"""
        if info.stream_type == StreamType.VIDEO_ONLY:
            self.pending_tab.video_files = [
                v for v in self.pending_tab.video_files
                if v.filepath != info.filepath
            ]
        elif info.stream_type == StreamType.AUDIO_ONLY:
            self.pending_tab.audio_files = [
                a for a in self.pending_tab.audio_files
                if a.filepath != info.filepath
            ]
        self.pending_tab._refresh_table()

    def _on_preview(self, filepath: str):
        """预览文件"""
        try:
            os.startfile(filepath)
        except Exception as e:
            QMessageBox.warning(self, "预览失败", f"无法打开文件:\n{e}")

    def _on_mark_complete(self, info: StreamInfo):
        """标记文件为已完整"""
        self._remove_from_pending(info)
        self._update_status()

    def _on_pending_remove(self, infos: list[StreamInfo]):
        """从待整理中移除选中的文件"""
        for info in infos:
            self._remove_from_pending(info)
        self._update_status()

    def _on_remux_requested(self, indices: list[int]):
        """转封装选中的 muxed 文件"""
        output_dir = self.settings_panel.get_output_dir()
        if not output_dir:
            QMessageBox.warning(self, "提示", "请先设置输出目录")
            return

        fmt = self.settings_panel.get_output_format()
        infos = self.muxed_tab.infos
        selected = [infos[i] for i in indices if i < len(infos)]

        if not selected:
            return

        success_count = 0
        fail_count = 0

        for info in selected:
            name = os.path.splitext(os.path.basename(info.filepath))[0]
            output_path = os.path.join(output_dir, f"{name}.{fmt}")

            success, error = remux_single(
                info.filepath, output_path,
                progress_callback=lambda s: self.task_status_label.setText(s),
            )

            if success:
                success_count += 1
                self.muxed_tab.set_status(info.filepath, "success")
            else:
                fail_count += 1
                self.muxed_tab.set_status(info.filepath, "error")
                logger.error(f"转封装失败: {info.filepath} - {error}")

        QMessageBox.information(
            self, "转封装完成",
            f"成功: {success_count} 个\n失败: {fail_count} 个",
        )
        self._update_status()

    def _on_batch_rename(self, rows: list[int]):
        """批量命名"""
        tasks = self.merge_queue_tab.get_tasks()
        selected_tasks = [tasks[r] for r in rows if r < len(tasks)]

        if len(selected_tasks) < 2:
            return

        dialog = BatchRenameDialog(len(selected_tasks), self)
        if dialog.exec() == BatchRenameDialog.Accepted:
            prefix, start, digits = dialog.get_result()
            if not prefix:
                QMessageBox.warning(self, "提示", "前缀不能为空")
                return

            for i, task in enumerate(selected_tasks):
                task.output_name = f"{prefix}_{start + i:0{digits}d}"

            self.merge_queue_tab._refresh_table()
            self._update_all_output_paths()
            self._update_status()

    def _find_root(self, filepath: str) -> str:
        """查找文件所属的根路径"""
        file_dir = os.path.dirname(filepath)
        for root in self.root_paths:
            try:
                common = os.path.commonpath([root, file_dir])
                if common == root:
                    return root
            except ValueError:
                continue
        return self.root_paths[0] if self.root_paths else ""

    def _auto_set_output_dir(self):
        """自动填充输出目录（如果未设置）"""
        from PySide6.QtWidgets import QFileDialog
        output_dir = self.settings_panel.get_output_dir()
        if output_dir:
            return
        # 用第一个源目录的父级作为默认输出目录
        if self.root_paths:
            parent = os.path.dirname(os.path.abspath(self.root_paths[0]))
            if parent and os.path.isdir(parent):
                self.settings_panel.dir_edit.setText(parent)

    def _update_all_output_paths(self):
        """更新所有任务的预计输出路径"""
        output_dir = self.settings_panel.get_output_dir()
        fmt = self.settings_panel.get_output_format()

        if not output_dir:
            return

        paths = []
        for task in self.merge_queue_tab.get_tasks():
            path = generate_output_path(
                output_dir,
                task.source_dir,
                task.root_path,
                task.output_name,
                fmt,
            )
            paths.append(path)

        self.merge_queue_tab.update_output_paths(paths)

    def _on_start_merge(self):
        """开始合并按钮点击"""
        if self.is_merging:
            return

        output_dir = self.settings_panel.get_output_dir()
        if not output_dir:
            QMessageBox.warning(self, "提示", "请先设置输出目录")
            return

        # 获取勾选的任务
        checked_indices = self.merge_queue_tab.get_checked_indices()
        if not checked_indices:
            QMessageBox.warning(self, "提示", "请先在合并队列中勾选要合并的任务")
            return

        tasks = self.merge_queue_tab.get_tasks()

        # 检查输出目录是否存在
        if not os.path.exists(output_dir):
            reply = QMessageBox.question(
                self, "创建目录",
                f"输出目录不存在:\n{output_dir}\n\n是否创建？",
                QMessageBox.Yes | QMessageBox.No,
            )
            if reply == QMessageBox.No:
                return
            try:
                os.makedirs(output_dir, exist_ok=True)
            except OSError as e:
                QMessageBox.critical(self, "错误", f"创建输出目录失败:\n{e}")
                return

        self.is_merging = True
        self.settings_panel.set_start_enabled(False)
        self.add_folder_btn.setEnabled(False)
        self.clear_btn.setEnabled(False)

        # 准备任务数据（仅勾选的任务）
        fmt = self.settings_panel.get_output_format()

        merge_tasks = []
        for original_idx in checked_indices:
            task = tasks[original_idx]
            output_path = generate_output_path(
                output_dir,
                task.source_dir,
                task.root_path,
                task.output_name,
                fmt,
            )
            merge_tasks.append({
                "original_index": original_idx,
                "video_file": task.video_file,
                "audio_file": task.audio_file,
                "output_path": output_path,
                "output_name": task.output_name,
            })

        # 启动合并线程
        self._start_merge_thread(merge_tasks)

    def _start_merge_thread(self, tasks: list[dict]):
        """启动合并线程"""
        signals = MergeSignals()
        signals.progress.connect(self._on_merge_progress)
        signals.task_status.connect(self._on_task_status)
        signals.finished.connect(self._on_merge_finished)
        # 冲突对话框通过 Signal 安全地跨线程传递
        signals.conflict_requested.connect(self._show_conflict_dialog_sync)

        # 使用事件循环和信号来同步处理冲突对话框
        self._conflict_event = threading.Event()
        self._conflict_result = [ConflictStrategy.OVERWRITE, False]  # [strategy, apply_all]

        def merge_worker():
            results: list[MergeResult] = []
            total = len(tasks)
            conflict_strategy = ConflictStrategy.OVERWRITE
            applied_all = False

            for i, task in enumerate(tasks):
                original_idx = task.get("original_index", i)
                video_file = task["video_file"]
                audio_file = task["audio_file"]
                output_path = task["output_path"]
                output_name = task.get("output_name", os.path.basename(output_path))

                signals.progress.emit(i + 1, total, f"正在合并: {output_name}")

                # 处理重名冲突
                actual_path = output_path
                if os.path.exists(output_path) and not applied_all:
                    # 通过 Signal 安全地通知主线程显示对话框，等待用户选择
                    self._conflict_event.clear()
                    signals.progress.emit(i + 1, total, f"文件已存在: {output_name}")
                    signals.conflict_requested.emit(output_path)
                    self._conflict_event.wait()  # 等待用户选择

                    strategy = self._conflict_result[0]
                    apply_all = self._conflict_result[1]

                    if strategy == ConflictStrategy.SKIP:
                        results.append(MergeResult(
                            task_index=original_idx,
                            output_name=output_name,
                            output_path=output_path,
                            success=False,
                            error_message="已跳过（文件已存在）",
                        ))
                        signals.task_status.emit(i, False, "已跳过（文件已存在）")
                        continue
                    elif strategy == ConflictStrategy.RENAME:
                        base, ext = os.path.splitext(output_path)
                        counter = 1
                        while True:
                            new_path = f"{base}_{counter}{ext}"
                            if not os.path.exists(new_path):
                                actual_path = new_path
                                break
                            counter += 1
                    conflict_strategy = strategy
                    applied_all = apply_all

                elif os.path.exists(output_path) and applied_all:
                    if conflict_strategy == ConflictStrategy.SKIP:
                        results.append(MergeResult(
                            task_index=original_idx,
                            output_name=output_name,
                            output_path=output_path,
                            success=False,
                            error_message="已跳过（文件已存在）",
                        ))
                        signals.task_status.emit(i, False, "已跳过（文件已存在）")
                        continue
                    elif conflict_strategy == ConflictStrategy.RENAME:
                        base, ext = os.path.splitext(output_path)
                        counter = 1
                        while True:
                            new_path = f"{base}_{counter}{ext}"
                            if not os.path.exists(new_path):
                                actual_path = new_path
                                break
                            counter += 1

                # 执行合并
                success, error = merge_single(
                    video_file, audio_file, actual_path,
                )

                result = MergeResult(
                    task_index=original_idx,
                    output_name=output_name,
                    output_path=actual_path,
                    success=success,
                    error_message=error,
                )
                results.append(result)
                signals.task_status.emit(original_idx, success, error)

            signals.finished.emit(results)

        thread = threading.Thread(target=merge_worker, daemon=True)
        thread.start()

    def _show_conflict_dialog_sync(self, output_path: str):
        """在主线程显示冲突对话框（由 QTimer.callOnMainThread 调用）"""
        dialog = ConflictDialog(output_path, self)
        ret = dialog.exec()

        if ret == 1:  # 覆盖
            self._conflict_result[0] = ConflictStrategy.OVERWRITE
        elif ret == 2:  # 重命名
            self._conflict_result[0] = ConflictStrategy.RENAME
        elif ret == 3:  # 跳过
            self._conflict_result[0] = ConflictStrategy.SKIP

        self._conflict_result[1] = dialog.is_apply_all()
        self._conflict_event.set()

    @Slot(int, int, str)
    def _on_merge_progress(self, current: int, total: int, text: str):
        """合并进度更新"""
        self.progress_bar.setMaximum(total)
        self.progress_bar.setValue(current)
        self.progress_bar.setFormat(f"{current}/{total}")
        self.task_status_label.setText(text)

    @Slot(int, bool, object)
    def _on_task_status(self, index: int, success: bool, error_msg: object):
        """单个任务状态更新"""
        self.merge_queue_tab.update_task_status(
            index, success,
            str(error_msg) if error_msg else None,
        )

    @Slot(list)
    def _on_merge_finished(self, results: list[MergeResult]):
        """合并完成"""
        self.is_merging = False
        self.add_folder_btn.setEnabled(True)
        self.clear_btn.setEnabled(True)

        success_count = sum(1 for r in results if r.success)
        fail_count = sum(1 for r in results if not r.success)

        # 显示结果摘要
        summary = ResultSummaryDialog(success_count, fail_count, self)
        summary.exec()

        # 处理删除源文件
        if (
            success_count > 0
            and self.settings_panel.is_delete_allowed()
        ):
            delete_dialog = DeleteConfirmDialog(success_count * 2, self)
            if delete_dialog.exec() == DeleteConfirmDialog.Accepted:
                self._delete_source_files(results)

        self._update_status()

    def _delete_source_files(self, results: list[MergeResult]):
        """删除已成功合并的源文件"""
        tasks = self.merge_queue_tab.get_tasks()
        deleted_count = 0

        for result in results:
            if not result.success:
                continue
            if result.task_index < len(tasks):
                task = tasks[result.task_index]
                for filepath in [task.video_file, task.audio_file]:
                    try:
                        if os.path.exists(filepath):
                            # 尝试使用 send2trash
                            try:
                                import send2trash
                                send2trash.send2trash(filepath)
                            except ImportError:
                                # 退化为 os.remove
                                os.remove(filepath)
                                logger.warning(f"send2trash 不可用，已永久删除: {filepath}")
                            deleted_count += 1
                    except Exception as e:
                        logger.error(f"删除文件失败: {filepath} - {e}")

        if deleted_count > 0:
            QMessageBox.information(
                self, "删除完成",
                f"已删除 {deleted_count} 个源文件",
            )

    # === 拖拽支持 ===
    def dragEnterEvent(self, event: QDragEnterEvent):
        """拖拽进入事件"""
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent):
        """拖拽放下事件"""
        urls = event.mimeData().urls()
        m4s_files = []
        for url in urls:
            if url.isLocalFile():
                path = url.toLocalFile()
                if os.path.isdir(path):
                    self._add_folder(path)
                elif path.lower().endswith(".m4s"):
                    m4s_files.append(path)
        if m4s_files:
            self._add_files(m4s_files)
