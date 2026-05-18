import os
import time
import re
from PySide6.QtWidgets import (
    QWidget,
    QHBoxLayout,
    QVBoxLayout,
    QLabel,
    QProgressBar,
    QScrollArea,
    QFrame,
)
from PySide6.QtCore import Qt, QPropertyAnimation, Slot, QEasingCurve, QSize

class ActiveTaskCard(QFrame):
    """单任务并发卡片"""

    def __init__(self, task_index: int, task_name: str, total_bytes: int, parent=None):
        super().__init__(parent)
        self.task_index = task_index
        self.task_name = task_name
        self.total_bytes = total_bytes
        self.start_time = time.time()

        self.setFrameShape(QFrame.StyledPanel)
        self.setFrameShadow(QFrame.Raised)
        
        # 极简美学玻璃拟态与霓虹暗光渐变
        self.setStyleSheet(
            "ActiveTaskCard {"
            "   background-color: rgba(30, 30, 45, 140);"
            "   border: 1px solid rgba(76, 175, 80, 100);"
            "   border-radius: 6px;"
            "}"
        )
        self.setFixedWidth(260)
        self.setFixedHeight(64)

        # 布局
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(4)

        # 标题栏：[合并中] 任务名
        title_layout = QHBoxLayout()
        title_layout.setContentsMargins(0, 0, 0, 0)
        
        status_tag = QLabel("[合并中]")
        status_tag.setStyleSheet("color: #4CAF50; font-size: 11px; font-weight: bold;")
        title_layout.addWidget(status_tag)

        # 截短任务名防溢出
        display_name = task_name
        if len(display_name) > 16:
            display_name = display_name[:14] + "..."
        self.name_label = QLabel(display_name)
        self.name_label.setStyleSheet("color: #ffffff; font-size: 11px; font-weight: 500;")
        title_layout.addWidget(self.name_label, 1)

        layout.addLayout(title_layout)

        # 仪表数据栏
        self.stats_label = QLabel("正在初始化...")
        self.stats_label.setStyleSheet("color: #aaaaaa; font-size: 10px;")
        layout.addWidget(self.stats_label)

        # 微型进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setFixedHeight(4)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setStyleSheet(
            "QProgressBar {"
            "   border: none;"
            "   background-color: rgba(255, 255, 255, 20);"
            "   border-radius: 2px;"
            "}"
            "QProgressBar::chunk {"
            "   background-color: #4CAF50;"
            "   border-radius: 2px;"
            "}"
        )
        layout.addWidget(self.progress_bar)

    def update_progress(self, progress_text: str):
        """流式解析百分比、速度与 ETA (C-3)"""
        pct_match = re.search(r"(\d+(?:\.\d+)?)%", progress_text)
        if not pct_match:
            return

        pct = float(pct_match.group(1))
        self.progress_bar.setValue(int(pct))

        # 计算耗时与速度
        elapsed = time.time() - self.start_time
        if pct > 0:
            # 估算总时间
            total_est = elapsed / (pct / 100.0)
            eta = max(0.0, total_est - elapsed)
            
            # 估算吞吐速度
            processed_bytes = self.total_bytes * (pct / 100.0)
            speed_bps = processed_bytes / elapsed if elapsed > 0 else 0
            
            # 格式化速度与剩余时间
            speed_str = self._format_speed(speed_bps)
            eta_str = f"剩余 {int(eta)}秒" if eta > 0.5 else "即将完成"
            
            self.stats_label.setText(f"{pct:.1f}% | {eta_str} | {speed_str}")
        else:
            self.stats_label.setText("正在解析...")

    def _format_speed(self, speed_bps: float) -> str:
        """格式化吞吐速率"""
        mb = speed_bps / (1024 * 1024)
        if mb >= 1.0:
            return f"{mb:.1f} MB/s"
        kb = speed_bps / 1024
        return f"{kb:.0f} KB/s"


class ActiveTasksDashboard(QScrollArea):
    """底部并发卡片式仪表盘"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.setFixedHeight(82)
        
        # 极简半透明磨砂黑设计
        self.setStyleSheet(
            "ActiveTasksDashboard {"
            "   border: none;"
            "   background-color: transparent;"
            "}"
            "QScrollBar:horizontal {"
            "   height: 4px;"
            "   background: transparent;"
            "}"
            "QScrollBar::handle:horizontal {"
            "   background: rgba(255, 255, 255, 30);"
            "   border-radius: 2px;"
            "}"
            "QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {"
            "   width: 0px;"
            "}"
        )

        # 视口内容容器
        self.content_widget = QWidget()
        self.content_widget.setStyleSheet("background-color: transparent;")
        self.setWidget(self.content_widget)

        # 水平排列卡片
        self.card_layout = QHBoxLayout(self.content_widget)
        self.card_layout.setContentsMargins(6, 6, 6, 6)
        self.card_layout.setSpacing(10)
        self.card_layout.addStretch()

        self.cards: dict[int, ActiveTaskCard] = {}
        self.setVisible(False)

    def add_task(self, task_index: int, task_name: str, total_bytes: int):
        """平滑追加一个新的监控卡片 (C-3)"""
        if task_index in self.cards:
            return

        # 创建卡片
        card = ActiveTaskCard(task_index, task_name, total_bytes, self)
        
        # 插入到 Stretch 之前
        self.card_layout.insertWidget(self.card_layout.count() - 1, card)
        self.cards[task_index] = card

        # 显示面板并执行滑动拉伸动效
        self.setVisible(True)

        # 动画：卡片宽度拉伸
        card.setFixedWidth(0)
        anim = QPropertyAnimation(card, b"minimumWidth", self)
        anim.setDuration(300)
        anim.setStartValue(0)
        anim.setEndValue(260)
        anim.setEasingCurve(QEasingCurve.OutCubic)
        anim.start()
        
        # 同步更新最大宽度，避免限制
        card.setMaximumWidth(260)

    def update_task(self, task_index: int, progress_text: str):
        """流式更新单个卡片的内部状态仪表 (C-3)"""
        if task_index in self.cards:
            self.cards[task_index].update_progress(progress_text)

    def remove_task(self, task_index: int):
        """平滑折叠淡出并析构指定的卡片 (C-3)"""
        if task_index not in self.cards:
            return

        card = self.cards[task_index]
        del self.cards[task_index]

        # 宽度收缩动效
        anim = QPropertyAnimation(card, b"maximumWidth", self)
        anim.setDuration(250)
        anim.setStartValue(260)
        anim.setEndValue(0)
        anim.setEasingCurve(QEasingCurve.InCubic)
        
        def on_finished():
            card.deleteLater()
            # 若全部卡片监控完毕，自动缩回折叠面板
            if not self.cards:
                self.setVisible(False)

        anim.finished.connect(on_finished)
        anim.start()

    def clear_all(self):
        """清空所有卡片并隐藏面板"""
        for card in list(self.cards.values()):
            card.deleteLater()
        self.cards.clear()
        self.setVisible(False)
