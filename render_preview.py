"""Render the actual UI using only fresh example data; never reads user tasks."""
import tempfile
from pathlib import Path
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt, QRectF, QPointF
from PySide6.QtGui import QImage, QPainter, QColor, QFont, QLinearGradient
from PySide6.QtTest import QTest
import main

app = QApplication([])
app.setStyle('Fusion')
with tempfile.TemporaryDirectory() as folder:
    main.DATA_FILE = str(Path(folder) / 'absent.json')
    data = main.load_data()
    for task, stars in zip(data['tasks'], (2, 3, 1)):
        task['importance'] = stars
    group = main.Group(data)
    group.show()
    QTest.qWait(100)
    widget = group.grab()
    canvas = QImage(1400, 820, QImage.Format_ARGB32)
    p = QPainter(canvas)
    p.setRenderHint(QPainter.Antialiasing)
    gradient = QLinearGradient(0, 0, 1400, 820)
    gradient.setColorAt(0, QColor('#F6FFFB'))
    gradient.setColorAt(1, QColor('#E6F5FF'))
    p.fillRect(canvas.rect(), gradient)
    p.setPen(Qt.NoPen)
    p.setBrush(QColor('#CDFAEA'))
    p.drawEllipse(QRectF(1080, -100, 500, 500))
    p.setBrush(QColor('#DDF2FF'))
    p.drawEllipse(QRectF(-180, 640, 650, 650))
    def text(x, y, value, size, color, bold=False):
        font = QFont(main.FONT)
        font.setPixelSize(size)
        font.setBold(bold)
        p.setFont(font)
        p.setPen(QColor(color))
        p.drawText(QPointF(x, y), value)
    text(90, 135, 'CAT COUNTDOWN  /  WINDOWS', 18, '#368B80', True)
    text(86, 244, '猫猫倒计时', 68, '#183F43', True)
    text(91, 313, '日子有盼头，桌面有小猫。', 31, '#54807D')
    text(91, 411, '安装，打开，就能用。', 27, '#275A57', True)
    text(91, 465, '倒计时 · 星级标记 · 自动排序', 24, '#527A7A')
    p.setPen(Qt.NoPen)
    p.setBrush(QColor('#218575'))
    p.drawRoundedRect(QRectF(90, 519, 315, 61), 18, 18)
    text(119, 560, '免费下载 Windows 版', 23, '#FFFFFF', True)
    text(91, 655, '离线使用  /  无需登录  /  免费开源', 20, '#4E8079')
    p.drawPixmap(745, 160, widget)
    text(92, 769, 'github.com/aijieli1/cat-countdown', 18, '#67948C')
    p.end()
    Path('assets').mkdir(exist_ok=True)
    assert canvas.save('assets/hero.png')
    widget.save('assets/widget.png')
    box = main.InputBox(group.add, group.update_task)
    box.popup(data['tasks'][1])
    QTest.qWait(50)
    box.grab().save('assets/edit.png')
    box.close()
    group.close()
