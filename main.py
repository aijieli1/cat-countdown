"""猫猫倒计时 · 离线 Windows 桌面组件。"""
import ctypes
import hashlib
from ctypes import wintypes
import json
import os
from pathlib import Path
import re
import sys
import uuid
import winreg
from datetime import date, timedelta

from PySide6.QtCore import (
    Qt, QPoint, QPointF, QRectF, QTimer, QSaveFile, QIODevice, QLockFile,
    QPropertyAnimation, QAbstractNativeEventFilter, Signal,
)
from PySide6.QtGui import QColor, QFont, QFontMetrics, QPainter, QPainterPath, QPen, QIcon, QPixmap, QCursor
from PySide6.QtNetwork import QLocalServer, QLocalSocket
from PySide6.QtWidgets import (
    QApplication, QWidget, QDialog, QLabel, QLineEdit, QPushButton, QVBoxLayout,
    QHBoxLayout, QScrollArea, QGraphicsOpacityEffect, QSystemTrayIcon, QMenu, QMessageBox,
)

APP = "CountdownWidget"
DATA_DIR = os.path.join(os.environ.get("LOCALAPPDATA", str(Path.home())), APP)
DATA_FILE = os.path.join(DATA_DIR, "tasks.json")
RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
FONT = "Microsoft YaHei UI"
WIDTH = 432
COLORS = ["#ECDDE1", "#DDE6EE", "#E4DFED", "#DEE8E0", "#EEE4D7"]
INK = "#28252C"


def load_data():
    try:
        with open(DATA_FILE, encoding="utf-8") as stream:
            data = json.load(stream)
    except FileNotFoundError:
        return {"tasks": [
            {"id": f"welcome-{index}", "date": (date.today() + timedelta(days=days)).isoformat(),
             "title": title, "c": index}
            for index, (days, title) in enumerate([
                (0, "示例 · 点圆圈完成"), (1, "示例 · 点笔修改日期"), (7, "示例 · 写下期待的事")])
        ], "pos": None, "seq": 3}
    if not isinstance(data, dict) or not isinstance(data.get("tasks"), list):
        raise ValueError("任务文件格式不正确")
    for task in data["tasks"]:
        date.fromisoformat(task["date"])
        if type(task.get('importance', 0)) is not int or not 0 <= task.get('importance', 0) <= 5:
            raise ValueError('重要程度必须是0到5颗星')
        if not isinstance(task["title"], str) or not isinstance(task.get("c", 0), int):
            raise ValueError("任务内容格式不正确")
    pos = data.get("pos")
    if pos is not None and (not isinstance(pos, list) or len(pos) != 2 or
                            not all(isinstance(n, int) for n in pos)):
        raise ValueError("位置记录格式不正确")
    data.setdefault("seq", 0)
    if not isinstance(data["seq"], int):
        raise ValueError("任务序号格式不正确")
    return data


def save_data(data):
    try:
        Path(DATA_DIR).mkdir(parents=True, exist_ok=True)
        content = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
        output = QSaveFile(DATA_FILE)
        if not output.open(QIODevice.WriteOnly) or output.write(content) != len(content) or not output.commit():
            raise OSError(output.errorString())
        return True
    except OSError as error:
        QMessageBox.warning(None, "未能保存", f"这次更改没有保存，原任务仍然保留。\n{error}")
        return False


def days_text(iso, today=None):
    days = (date.fromisoformat(iso) - (today or date.today())).days
    if days < 0:
        return f"已过期 {-days} 天"
    if days == 0:
        return "今天"
    if days == 1:
        return "明天"
    return f"还有 {days} 天"


def parse_task(text, today=None):
    today = today or date.today()
    parts = text.strip().split(maxsplit=1)
    if len(parts) != 2 or not parts[1].strip():
        return None
    token, title = parts
    relative = {"今天": 0, "今日": 0, "明天": 1, "后天": 2}
    try:
        if token in relative:
            target = today + timedelta(days=relative[token])
        elif re.fullmatch(r"\d{4}-\d{1,2}-\d{1,2}", token):
            target = date(*map(int, token.split("-")))
        else:
            match = re.fullmatch(r"(\d{1,2})月(\d{1,2})[日号]?", token)
            if not match:
                return None
            month, day = map(int, match.groups())
            target = None
            for year in range(today.year, min(today.year + 9, 10000)):
                try:
                    candidate = date(year, month, day)
                except ValueError:
                    continue
                if candidate >= today:
                    target = candidate
                    break
            if target is None:
                return None
    except (ValueError, OverflowError):
        return None
    return target.isoformat(), title.strip()


def label(text="", size=11, bold=False):
    result = QLabel(text)
    font = QFont(FONT)
    font.setPointSizeF(size)
    font.setBold(bold)
    result.setFont(font)
    result.setTextFormat(Qt.PlainText)
    result.setStyleSheet(f"color: {INK}; background: transparent;")
    result.setAttribute(Qt.WA_TransparentForMouseEvents)
    return result


def paint_panel(painter, rect, color, radius=17):
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setPen(Qt.NoPen)
    # 将阴影画在预留区域内，滚动或透明窗口均不会裁断效果。
    for spread in range(10, 0, -1):
        painter.setBrush(QColor(40, 40, 40, 6))
        painter.drawRoundedRect(rect.adjusted(-spread, -spread + 5, spread, spread + 5),
                                radius + spread, radius + spread)
    painter.setBrush(color)
    painter.setPen(QPen(QColor(255, 255, 255, 175), 1))
    painter.drawRoundedRect(rect, radius, radius)


class DragSurface(QWidget):
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.window().drag_offset = event.globalPosition().toPoint() - self.window().pos()
            event.accept()

    def mouseMoveEvent(self, event):
        offset = getattr(self.window(), "drag_offset", None)
        if offset is not None and event.buttons() & Qt.LeftButton:
            self.window().move(event.globalPosition().toPoint() - offset)
            event.accept()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton and getattr(self.window(), "drag_offset", None) is not None:
            self.window().drag_offset = None
            self.window().remember_position()
            event.accept()


class Cat(DragSurface):
    def __init__(self):
        super().__init__()
        self.setFixedHeight(67)
        self.setToolTip("拖动猫猫或卡片，放到喜欢的位置")

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        outline = QColor("#B79982")
        coat = QColor("#F2DDC6")
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(42, 31, 48, 28))
        p.drawEllipse(QRectF(20, 54, 120, 9))
        tail = QPainterPath(QPointF(113, 47))
        tail.cubicTo(145, 59, 145, 27, 130, 35)
        p.setPen(QPen(outline, 9, Qt.SolidLine, Qt.RoundCap))
        p.drawPath(tail)
        p.setPen(QPen(coat, 6, Qt.SolidLine, Qt.RoundCap))
        p.drawPath(tail)
        p.setPen(QPen(outline, 1.3))
        p.setBrush(coat)
        p.drawEllipse(QRectF(64, 30, 63, 29))
        head = QPainterPath(QPointF(29, 33))
        head.lineTo(28, 13)
        head.quadTo(29, 9, 33, 13)
        head.lineTo(45, 23)
        head.quadTo(55, 19, 65, 23)
        head.lineTo(77, 13)
        head.quadTo(81, 10, 81, 16)
        head.lineTo(81, 34)
        head.cubicTo(92, 60, 22, 67, 29, 33)
        p.drawPath(head)
        p.setPen(QPen(QColor("#D6B5A5"), 3, Qt.SolidLine, Qt.RoundCap))
        p.drawLine(QPointF(34, 20), QPointF(35, 28))
        p.drawLine(QPointF(75, 21), QPointF(74, 28))
        p.setPen(QPen(QColor("#725D54"), 1.8, Qt.SolidLine, Qt.RoundCap))
        for x in (39, 62):
            eye = QPainterPath(QPointF(x, 38))
            eye.quadTo(x + 5, 44, x + 10, 38)
            p.drawPath(eye)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor("#EABBB5"))
        p.drawEllipse(QRectF(32, 44, 10, 5))
        p.drawEllipse(QRectF(71, 44, 10, 5))
        p.drawEllipse(QRectF(53, 43, 5, 3))
        p.setPen(QPen(outline, 1.2))
        p.setBrush(coat)
        p.drawEllipse(QRectF(31, 53, 21, 10))
        p.drawEllipse(QRectF(58, 53, 21, 10))
        p.setFont(QFont(FONT, 10))
        p.setPen(QColor("#A597AA"))
        p.drawText(QPointF(98, 22), "z")
        p.setFont(QFont(FONT, 8))
        p.drawText(QPointF(111, 13), "z")


class CompleteButton(QPushButton):
    def __init__(self, title):
        super().__init__()
        self.setFixedSize(30, 34)
        self.setCheckable(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setAccessibleName(f"完成：{title}")
        self.setToolTip("完成这件事")

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(QPen(QColor("#9C8F9F"), 1.5))
        p.setBrush(QColor("#9C8F9F") if self.isChecked() else
                   QColor(255, 255, 255, 125 if self.underMouse() else 50))
        p.drawEllipse(QRectF(6, 8, 18, 18))
        if self.isChecked():
            p.setPen(QPen(Qt.white, 1.8, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
            path = QPainterPath(QPointF(11, 17))
            path.lineTo(14, 20)
            path.lineTo(20, 13)
            p.drawPath(path)
        if self.hasFocus():
            p.setBrush(Qt.NoBrush)
            p.setPen(QPen(QColor("#76647F"), 1, Qt.DotLine))
            p.drawRoundedRect(QRectF(2, 3, 26, 28), 8, 8)


class Stars(QWidget):
    def __init__(self, value=0, on_change=None):
        super().__init__()
        self.value = value
        self.on_change = on_change
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(1)
        self.buttons = []
        for number in range(1, 6):
            button = QPushButton()
            button.setAutoDefault(False)
            button.setFixedSize(19, 20)
            button.setCursor(Qt.PointingHandCursor)
            button.setCheckable(True)
            button.setAccessibleName(f'重要程度 {number} 星')
            button.setToolTip(f'标为 {number} 星；再次点击当前星级可清除')
            button.setStyleSheet('QPushButton { padding: 0; border: none; border-radius: 4px; background: transparent; color: #9A742F; font-size: 16px; } QPushButton:hover,QPushButton:focus { background: rgba(255,255,255,150); }')
            button.clicked.connect(lambda checked=False, n=number: self.choose(n))
            row.addWidget(button)
            self.buttons.append(button)
        self.setFixedSize(99, 20)
        self.set_value(value)

    def set_value(self, value):
        self.value = value
        for number, button in enumerate(self.buttons, 1):
            button.setText('★' if number <= value else '☆')
            button.setChecked(number <= value)

    def choose(self, number):
        value = 0 if self.value == number else number
        if self.on_change is None or self.on_change(value):
            self.set_value(value)
        else:
            self.set_value(self.value)


class Card(DragSurface):
    def __init__(self, task, on_done, on_edit, on_rate):
        super().__init__()
        self.task = task
        self.on_done = on_done
        self.on_edit = on_edit
        self.setFixedHeight(80)
        self._fading = False
        row = QHBoxLayout(self)
        row.setContentsMargins(23, 10, 27, 21)
        row.setSpacing(7)
        self.dot = CompleteButton(task["title"])
        self.dot.clicked.connect(self.complete)
        row.addWidget(self.dot)
        self.count = label(size=11.5, bold=True)
        row.addWidget(self.count)
        divider = label("│", 10)
        divider.setStyleSheet("color: rgba(75,65,83,45); background: transparent;")
        row.addWidget(divider)
        self.title = label(size=11.5, bold=True)
        content = QWidget()
        details = QVBoxLayout(content)
        details.setContentsMargins(0, 0, 0, 0)
        details.setSpacing(2)
        self.stars = Stars(task.get('importance', 0), lambda value: on_rate(self.task, value))
        details.addWidget(self.stars, 0, Qt.AlignLeft)
        details.addWidget(self.title, 0, Qt.AlignLeft)
        row.addWidget(content, 1)
        self.edit_button = QPushButton("✎")
        self.edit_button.setFixedSize(24, 30)
        self.edit_button.setAccessibleName(f"编辑：{task['title']}")
        self.edit_button.setToolTip("修改日期和内容（也可双击卡片）")
        self.edit_button.setCursor(Qt.PointingHandCursor)
        self.edit_button.setStyleSheet("QPushButton { color: #897A90; background: transparent; border: none; border-radius: 6px; font-size: 20px; } QPushButton:hover,QPushButton:focus { background: rgba(255,255,255,140); }")
        self.edit_button.clicked.connect(lambda: self.on_edit(self.task))
        row.addWidget(self.edit_button)
        self.refresh()

    def refresh(self):
        countdown = days_text(self.task["date"])
        count_width = min(118, QFontMetrics(self.count.font()).horizontalAdvance(countdown) + 2)
        self.count.setFixedWidth(count_width)
        self.count.setText(QFontMetrics(self.count.font()).elidedText(countdown, Qt.ElideRight, count_width))
        self.setToolTip(f"{self.task['title']}\n{countdown} · {self.task['date']}\n双击修改日期和内容")
        self.title.setText(QFontMetrics(self.title.font()).elidedText(self.task["title"], Qt.ElideRight,
                                                                   max(30, self.width() - count_width - 150)))

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.LeftButton and not self._fading:
            self.window().drag_offset = None
            self.on_edit(self.task)
            event.accept()

    def resizeEvent(self, event):
        self.refresh()

    def paintEvent(self, event):
        color = QColor(COLORS[self.task.get("c", 0) % len(COLORS)])
        color.setAlpha(229)
        p = QPainter(self)
        paint_panel(p, QRectF(13, 5, self.width() - 26, 57), color)

    def complete(self):
        if self._fading:
            return
        self._fading = True
        self.dot.setEnabled(False)
        effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(effect)
        self.animation = QPropertyAnimation(effect, b"opacity", self)
        self.animation.setDuration(260)
        self.animation.setStartValue(1.0)
        self.animation.setEndValue(0.0)
        self.animation.finished.connect(lambda: self.on_done(self.task))
        self.animation.start()


class Group(DragSurface):
    edit_requested = Signal(object)
    def __init__(self, data):
        super().__init__()
        self.data = data
        self.drag_offset = None
        self.today = date.today()
        self.setWindowTitle("倒计时 · 猫猫待办")
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedWidth(WIDTH)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 10)
        layout.setSpacing(0)
        self.cat = Cat()
        layout.addWidget(self.cat)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }"
                                  "QScrollBar:vertical { background: transparent; width: 5px; }"
                                  "QScrollBar::handle:vertical { background: #B9ADB9; border-radius: 2px; min-height: 22px; }"
                                  "QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical { height: 0px; }"
                                  "QScrollBar::add-page:vertical,QScrollBar::sub-page:vertical { background: transparent; }")
        self.scroll.viewport().setAutoFillBackground(False)
        self.container = QWidget()
        self.container.setAutoFillBackground(False)
        self.cards_lay = QVBoxLayout(self.container)
        self.cards_lay.setContentsMargins(0, 0, 0, 0)
        self.cards_lay.setSpacing(0)
        self.cards_lay.setAlignment(Qt.AlignTop)
        self.scroll.setWidget(self.container)
        self.container.setAutoFillBackground(False)
        layout.addWidget(self.scroll)
        footer = QHBoxLayout()
        footer.addStretch()
        self.plus = QPushButton("＋")
        self.plus.setAccessibleName("添加任务")
        self.plus.setToolTip("添加任务 · Ctrl + Alt + T")
        self.plus.setFixedSize(38, 38)
        self.plus.setCursor(Qt.PointingHandCursor)
        self.plus.setStyleSheet("QPushButton { color: #706176; font: 22px 'Microsoft YaHei UI';"
                                "background: rgba(241,235,245,230); border: 1px solid #FFFFFF; border-radius: 19px; }"
                                "QPushButton:hover { background: #F9F5FC; }"
                                "QPushButton:focus { border: 2px solid #9883A6; }")
        footer.addWidget(self.plus)
        footer.addStretch()
        layout.addLayout(footer)
        self.rebuild()
        self.restore_position()
        self.timer = QTimer(self)
        self.timer.setInterval(15000)
        self.timer.timeout.connect(self.check_day)
        self.timer.start()

    def rebuild(self):
        while self.cards_lay.count():
            old = self.cards_lay.takeAt(0).widget()
            old.hide()
            old.deleteLater()
        tasks = sorted(self.data["tasks"], key=lambda task: task["date"])
        for task in tasks:
            self.cards_lay.addWidget(Card(task, self.remove, self.edit_requested.emit, self.set_importance))
        if not tasks:
            empty = label("今天也要从容一点。\n点一下 +，记下下一件事", 10.5)
            empty.setFixedHeight(80)
            empty.setAlignment(Qt.AlignCenter)
            empty.setStyleSheet("color: #554B5B; background: rgba(244,240,247,230); border: 1px solid white; border-radius: 17px; margin: 5px 13px 13px;")
            self.cards_lay.addWidget(empty)
        screen = self.screen().availableGeometry()
        height = min(max(1, len(tasks)) * 80, max(100, screen.height() - 190))
        self.container.setMinimumHeight(max(1, len(tasks)) * 80)
        self.scroll.setFixedHeight(height)
        self.setFixedHeight(67 + height + 48)

    def add(self, iso, title, importance=0):
        sequence = self.data.get("seq", 0) + 1
        if type(importance) is not int or not 0 <= importance <= 5:
            raise ValueError('重要程度必须是0到5颗星')
        task = {"id": uuid.uuid4().hex, "date": iso, "title": title, "c": sequence % len(COLORS), 'importance': importance}
        proposed = dict(self.data, seq=sequence, tasks=self.data["tasks"] + [task])
        if not save_data(proposed):
            return False
        self.data.update(proposed)
        self.rebuild()
        self.show()
        return True

    def remove(self, task):
        proposed = dict(self.data, tasks=[item for item in self.data["tasks"] if item is not task])
        if save_data(proposed):
            self.data.update(proposed)
        self.rebuild()

    def update_task(self, task, iso, title, importance=None):
        importance = task.get('importance', 0) if importance is None else importance
        if type(importance) is not int or not 0 <= importance <= 5:
            raise ValueError('重要程度必须是0到5颗星')
        replacement = dict(task, date=iso, title=title, importance=importance)
        proposed = dict(self.data, tasks=[replacement if item is task else item for item in self.data['tasks']])
        if not save_data(proposed):
            return False
        self.data.update(proposed)
        self.rebuild()
        return True

    def set_importance(self, task, value):
        if type(value) is not int or not 0 <= value <= 5:
            raise ValueError('重要程度必须是0到5颗星')
        replacement = dict(task, importance=value)
        proposed = dict(self.data, tasks=[replacement if item is task else item for item in self.data['tasks']])
        if not save_data(proposed):
            return False
        task['importance'] = value
        return True

    def check_day(self):
        if self.today != date.today():
            self.today = date.today()
            for index in range(self.cards_lay.count()):
                card = self.cards_lay.itemAt(index).widget()
                if isinstance(card, Card):
                    card.refresh()

    def restore_position(self):
        saved = self.data.get("pos")
        if saved and any(screen.availableGeometry().contains(QPoint(*saved)) for screen in QApplication.screens()):
            self.move(*saved)
            return
        screen = QApplication.primaryScreen().availableGeometry()
        self.move(screen.right() - self.width() - 35, screen.top() + 90)
        # 显示器拔掉时暂时显示在主屏，绝不覆盖原位置记录。

    def remember_position(self):
        proposed = dict(self.data, pos=[self.x(), self.y()])
        if save_data(proposed):
            self.data.update(proposed)

    def reveal(self):
        """用户主动找回窗口时临时移到主屏，只有拖动才保存新位置。"""
        area = QApplication.primaryScreen().availableGeometry()
        self.move(area.right() - self.width() - 35, area.top() + 90)
        self.showNormal()
        self.raise_()
        self.activateWindow()


class InputBox(QDialog):
    def __init__(self, on_create, on_update=None):
        super().__init__()
        self.on_create = on_create
        self.on_update = on_update
        self.editing_task = None
        self.setWindowTitle("添加倒计时")
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Tool | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedSize(450, 296)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 24, 30, 30)
        layout.setSpacing(12)
        top = QHBoxLayout()
        self.heading = label("记下一件小事", 14, True)
        top.addWidget(self.heading)
        top.addStretch()
        close = QPushButton("×")
        close.setAccessibleName("关闭")
        close.setFixedSize(28, 28)
        close.clicked.connect(self.reject)
        top.addWidget(close)
        layout.addLayout(top)
        layout.addWidget(label("让重要的日子，轻轻留在桌面上。", 10))
        self.edit = QLineEdit()
        self.edit.setAccessibleName("日期和事件")
        self.edit.setPlaceholderText("明天 交材料")
        self.edit.setMaxLength(200)
        self.edit.setFixedHeight(44)
        self.edit.returnPressed.connect(self.commit)
        layout.addWidget(self.edit)
        self.hint = label("例如：10月16日 开会  /  2026-10-16 开会", 9)
        layout.addWidget(self.hint)
        rating_row = QHBoxLayout()
        rating_row.addWidget(label('重要程度', 10))
        self.stars = Stars()
        rating_row.addWidget(self.stars)
        rating_row.addStretch()
        layout.addLayout(rating_row)
        bottom = QHBoxLayout()
        for word in ("今天", "明天", "后天"):
            chip = QPushButton(word)
            chip.clicked.connect(lambda checked=False, day=word: self.choose_day(day))
            bottom.addWidget(chip)
        bottom.addStretch()
        self.submit = QPushButton("添加  ↵")
        self.submit.setObjectName("submit")
        self.submit.setDefault(True)
        self.submit.clicked.connect(self.commit)
        bottom.addWidget(self.submit)
        layout.addLayout(bottom)
        self.setStyleSheet(f"QPushButton {{ color: #66576E; background: #EEE8F2; border: 1px solid transparent; border-radius: 9px; padding: 7px 10px; font: 10pt '{FONT}'; }}"
                          "QPushButton:hover { background: #E2D9EA; } QPushButton:focus { border: 1px solid #9B85AC; }"
                          "QPushButton#submit { background: #8D789D; color: white; padding: 8px 17px; }"
                          "QPushButton#submit:hover { background: #78638A; }"
                          f"QLineEdit {{ background: #FFFFFF; color: {INK}; border: 1px solid #DCD2E3; border-radius: 11px; padding: 0px 12px; font: 11pt '{FONT}'; selection-background-color: #D8CBE3; }}"
                          "QLineEdit:focus { border: 1px solid #A08BAB; }")

    def paintEvent(self, event):
        p = QPainter(self)
        paint_panel(p, QRectF(10, 5, self.width() - 20, self.height() - 21), QColor("#FAF7FB"), 21)

    def choose_day(self, day):
        text = self.edit.text().strip()
        parsed = parse_task(text)
        self.edit.setText(f"{day} {parsed[1] if parsed else text}")
        self.edit.setFocus()
        self.edit.setCursorPosition(len(self.edit.text()))

    def commit(self):
        task = parse_task(self.edit.text())
        if task is None:
            self.hint.setText("日期和事情之间加空格，并检查日期是否存在。")
            self.hint.setStyleSheet("color: #A55461; background: transparent;")
            self.edit.setFocus()
            return
        saved = self.on_update(self.editing_task, *task, self.stars.value) if self.editing_task is not None else self.on_create(*task, self.stars.value)
        if saved:
            self.accept()

    def popup(self, task=None):
        task = task if isinstance(task, dict) else None
        if self.isVisible() and task is None:
            self.raise_()
            self.activateWindow()
            return
        screen = QApplication.screenAt(QCursor.pos()) or QApplication.primaryScreen()
        area = screen.availableGeometry()
        self.move(area.center() - self.rect().center())
        self.editing_task = task
        self.stars.set_value(task.get('importance', 0) if task else 0)
        self.heading.setText("修改这件小事" if task else "记下一件小事")
        self.setWindowTitle("编辑倒计时" if task else "添加倒计时")
        self.submit.setText("保存  ↵" if task else "添加  ↵")
        self.edit.setText(f"{task['date']} {task['title']}" if task else "")
        self.hint.setText("例如：10月16日 开会  /  2026-10-16 开会")
        self.hint.setStyleSheet("color: #716477; background: transparent;")
        self.show()
        self.raise_()
        self.activateWindow()
        self.edit.setFocus()


class Hotkey(QAbstractNativeEventFilter):
    def __init__(self, callback):
        super().__init__()
        self.callback = callback
        self.registered = bool(ctypes.windll.user32.RegisterHotKey(None, 0xC071, 0x4003, 0x54))

    def nativeEventFilter(self, event_type, message):
        if bytes(event_type) in (b"windows_generic_MSG", b"windows_dispatcher_MSG"):
            msg = wintypes.MSG.from_address(int(message))
            if msg.message == 0x0312 and msg.wParam == 0xC071:
                self.callback()
                return True, 0
        return False, 0

    def close(self):
        if self.registered:
            ctypes.windll.user32.UnregisterHotKey(None, 0xC071)


def autostart_cmd():
    if getattr(sys, "frozen", False):
        return f'"{sys.executable}"'
    pythonw = Path(sys.executable).with_name("pythonw.exe")
    return f'"{pythonw if pythonw.exists() else sys.executable}" "{Path(__file__).resolve()}"'


def autostart_on():
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
            return bool(winreg.QueryValueEx(key, APP)[0])
    except OSError:
        return False


def set_autostart(enabled):
    try:
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
            if enabled:
                winreg.SetValueEx(key, APP, 0, winreg.REG_SZ, autostart_cmd())
            else:
                try:
                    winreg.DeleteValue(key, APP)
                except FileNotFoundError:
                    pass
        return True
    except OSError:
        return False


def make_icon():
    image = QPixmap(64, 64)
    image.fill(Qt.transparent)
    p = QPainter(image)
    p.setRenderHint(QPainter.Antialiasing)
    p.setPen(QPen(QColor("#A58D7A"), 2))
    p.setBrush(QColor("#F2DDC6"))
    path = QPainterPath(QPointF(12, 29))
    path.lineTo(12, 10)
    path.lineTo(26, 20)
    path.lineTo(38, 20)
    path.lineTo(52, 10)
    path.lineTo(52, 29)
    path.cubicTo(65, 64, -1, 64, 12, 29)
    p.drawPath(path)
    p.setPen(QPen(QColor("#766056"), 3, Qt.SolidLine, Qt.RoundCap))
    p.drawLine(QPointF(21, 35), QPointF(26, 37))
    p.drawLine(QPointF(38, 37), QPointF(43, 35))
    p.end()
    return QIcon(image)


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setFont(QFont(FONT, 11))
    app.setQuitOnLastWindowClosed(False)
    app.setWindowIcon(make_icon())
    if "--autostart-on" in sys.argv or "--autostart-off" in sys.argv:
        enabled = "--autostart-on" in sys.argv
        success = set_autostart(enabled)
        QMessageBox.information(None, "开机启动", ("已开启开机启动" if enabled else "已关闭开机启动") if success else "未能设置，请检查权限。")
        return
    Path(DATA_DIR).mkdir(parents=True, exist_ok=True)
    lock = QLockFile(os.path.join(DATA_DIR, "instance.lock"))
    lock.setStaleLockTime(0)
    server_name = APP + hashlib.sha256(os.path.normcase(DATA_DIR).encode()).hexdigest()[:16]
    if not lock.tryLock(100):
        socket = QLocalSocket()
        socket.connectToServer(server_name)
        if socket.waitForConnected(3000):
            socket.write(b"quit" if "--quit" in sys.argv else b"show")
            socket.waitForBytesWritten(1000)
            socket.waitForDisconnected(1500)
        elif "--quit" not in sys.argv:
            QMessageBox.information(None, "倒计时", "组件正在启动，请稍后再双击一次。")
        return
    if "--quit" in sys.argv:
        return
    try:
        data = load_data()
    except (OSError, ValueError, TypeError, KeyError) as error:
        QMessageBox.critical(None, "任务文件需要检查", f"没有改动原文件，请检查：\n{DATA_FILE}\n{error}")
        return
    group = Group(data)
    if not os.path.exists(DATA_FILE):
        save_data(data)
    QLocalServer.removeServer(server_name)
    server = QLocalServer(app)
    server.setSocketOptions(QLocalServer.UserAccessOption)

    def reveal_existing():
        while server.hasPendingConnections():
            connection = server.nextPendingConnection()
            def handle(connection=connection):
                message = bytes(connection.readAll())
                connection.disconnectFromServer()
                connection.deleteLater()
                if message == b"quit":
                    app.quit()
                elif message == b"show":
                    group.reveal()
            connection.readyRead.connect(handle)
            if connection.bytesAvailable():
                handle()

    server.newConnection.connect(reveal_existing)
    if not server.listen(server_name):
        QMessageBox.warning(None, "窗口找回入口不可用", "请使用托盘菜单显示组件。")
    box = InputBox(group.add, group.update_task)
    group.plus.clicked.connect(box.popup)
    group.edit_requested.connect(box.popup)
    tray = QSystemTrayIcon(make_icon(), app)
    tray.setToolTip("猫猫倒计时 · Ctrl + Alt + T")
    menu = QMenu()
    menu.addAction("新建任务", box.popup)
    menu.addAction("显示 / 隐藏", lambda: group.hide() if group.isVisible() else group.reveal())
    menu.addAction("退出", app.quit)
    tray.setContextMenu(menu)
    tray.activated.connect(lambda reason: box.popup() if reason == QSystemTrayIcon.Trigger else None)
    tray.show()
    hotkey = Hotkey(box.popup)
    app.installNativeEventFilter(hotkey)
    app.aboutToQuit.connect(hotkey.close)
    app.aboutToQuit.connect(lock.unlock)
    group.show()
    if "--reveal" in sys.argv:
        group.reveal()
    else:
        group.raise_()
    if not hotkey.registered:
        tray.showMessage("快捷键已被占用", "仍可点击桌面 + 或托盘图标添加任务。", QSystemTrayIcon.Information, 5000)
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
