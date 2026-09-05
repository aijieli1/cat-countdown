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
    group = main.Group(data)
    group.show()
    QTest.qWait(100)
    widget = group.grab()
    canvas = QImage(1400, 820, QImage.Format_ARGB32)
    p = QPainter(canvas)
    p.setRenderHint(QPainter.Antialiasing)
    gradient = QLinearGradient(0, 0, 1400, 820)
    gradient.setColorAt(0, QColor('#F9F5EF'))
    gradient.setColorAt(1, QColor('#EBE4F0'))
    p.fillRect(canvas.rect(), gradient)
    p.setPen(Qt.NoPen)
    p.setBrush(QColor('#F1E6DB'))
    p.drawEllipse(QRectF(1080, -100, 500, 500))
    p.setBrush(QColor('#E7E1EC'))
    p.drawEllipse(QRectF(-180, 640, 650, 650))
    def text(x, y, value, size, color, bold=False):
        font = QFont(main.FONT)
        font.setPixelSize(size)
        font.setBold(bold)
        p.setFont(font)
        p.setPen(QColor(color))
        p.drawText(QPointF(x, y), value)
    text(90, 135, 'CAT COUNTDOWN  /  WINDOWS', 18, '#927F9D', True)
    text(86, 244, '猫猫倒计时', 68, '#342C3C', True)
    text(91, 313, '小事，轻轻放在桌面上。', 31, '#75677C')
    text(91, 411, '安装，打开，就能用。', 27, '#433849', True)
    text(91, 465, '改日期 · 记事情 · 点一下完成', 24, '#74697C')
    p.setPen(Qt.NoPen)
    p.setBrush(QColor('#8D789D'))
    p.drawRoundedRect(QRectF(90, 519, 315, 61), 18, 18)
    text(119, 560, '免费下载 Windows 版', 23, '#FFFFFF', True)
    text(91, 655, '离线使用  /  无需登录  /  免费开源', 20, '#8A7C92')
    p.drawPixmap(745, 160, widget)
    text(92, 769, 'github.com/aijieli1/cat-countdown', 18, '#95879D')
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
