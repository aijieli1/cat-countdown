"""运行：python test_widget.py。只使用临时数据，不接触真实任务。"""
import json
import os
import tempfile
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch

from PySide6.QtCore import QPoint, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
import main as widget


def check():
    app = QApplication.instance() or QApplication([])
    app.setStyle("Fusion")
    with tempfile.TemporaryDirectory() as folder:
        widget.DATA_DIR = folder
        widget.DATA_FILE = os.path.join(folder, "tasks.json")
        today = date.today()
        initial = widget.load_data()
        assert len(initial['tasks']) == 3 and all('示例' in task['title'] for task in initial['tasks'])
        for offset, expected in [(0, "今天"), (1, "明天"), (7, "还有 7 天"), (-3, "已过期 3 天")]:
            assert widget.days_text((today + timedelta(days=offset)).isoformat()) == expected
        assert widget.parse_task("明天 交材料") == ((today + timedelta(days=1)).isoformat(), "交材料")
        assert widget.parse_task("2026-02-30 无效") is None
        assert widget.parse_task("今天") is None
        assert widget.parse_task("10月16日 开会")
        assert widget.parse_task("2月29日 闰日")
        assert widget.parse_task("2月29日 闰日", date(2026, 9, 5))[0] == "2028-02-29"
        assert widget.parse_task("1月1日 新年", date(2026, 9, 5))[0] == "2027-01-01"
        assert widget.parse_task("2026-01-01 已过期")[0] == "2026-01-01"
        data = {"pos": [100, 120], "seq": 0, "tasks": []}
        group = widget.Group(data)
        group.show()
        QTest.qWait(100)
        assert group.plus.isVisible() and group.pos() == QPoint(100, 120)
        box = widget.InputBox(group.add, group.update_task)
        group.plus.clicked.connect(box.popup)
        group.edit_requested.connect(box.popup)
        QTest.mouseClick(group.plus, Qt.LeftButton)
        assert box.isVisible()
        box.edit.setText("2026-02-30 保留输入")
        QTest.keyClick(box.edit, Qt.Key_Return)
        assert box.edit.text() == "2026-02-30 保留输入" and box.isVisible()
        box.edit.setText("明天 交材料")
        QTest.keyClick(box.edit, Qt.Key_Return)
        assert not box.isVisible() and len(data["tasks"]) == 1
        for offset, title in [(7, "提交季度报告"), (-3, "等待确认"), (0, "组会"), (42, "这是一个需要省略展示的很长很长的任务标题")]:
            assert group.add((today + timedelta(days=offset)).isoformat(), title)
        QTest.qWait(100)
        cards = [group.cards_lay.itemAt(i).widget() for i in range(group.cards_lay.count())]
        assert [c.task["date"] for c in cards] == sorted(t["date"] for t in data["tasks"])
        assert "…" in cards[-1].title.text()
        assert cards[-1].task["title"] in cards[-1].toolTip()
        group.grab().save(str(Path(__file__).with_name("preview.png")))
        box.popup()
        box.grab().save(str(Path(__file__).with_name("preview-input.png")))
        QTest.keyClick(box.edit, Qt.Key_Escape)
        assert not box.isVisible()
        QTest.mouseClick(cards[0].dot, Qt.LeftButton)
        assert cards[0].dot.isChecked()
        QTest.qWait(320)
        assert len(data["tasks"]) == 4
        # 编辑通过真实按钮进入，修改日期、标题后按新日期排序；取消不保存。
        card = group.cards_lay.itemAt(0).widget()
        original = card.task
        QTest.mouseClick(card.edit_button, Qt.LeftButton)
        assert box.editing_task is original and box.submit.text().startswith('保存')
        box.edit.setText('2026-02-30 无效编辑')
        QTest.keyClick(box.edit, Qt.Key_Return)
        assert box.isVisible() and original in data['tasks']
        box.edit.setText('2099-12-31 已改日期与内容')
        QTest.keyClick(box.edit, Qt.Key_Return)
        assert not box.isVisible() and len(data['tasks']) == 4
        assert group.cards_lay.itemAt(3).widget().task['title'] == '已改日期与内容'
        assert group.cards_lay.itemAt(3).widget().count.text().startswith('还有')
        edited = group.cards_lay.itemAt(3).widget().task
        box.popup(edited)
        box.edit.setText('今天 不应保存')
        QTest.keyClick(box.edit, Qt.Key_Escape)
        assert edited['title'] == '已改日期与内容'
        # 用户从猫猫区域拖动整个组，放开后记住位置。
        start = group.pos()
        QTest.mousePress(group.cat, Qt.LeftButton, pos=QPoint(150, 20))
        QTest.mouseMove(group.cat, QPoint(180, 40), delay=30)
        QTest.mouseRelease(group.cat, Qt.LeftButton, pos=QPoint(180, 40))
        assert group.pos() != start and data["pos"] == [group.x(), group.y()]
        restored = widget.load_data()
        assert restored == data
        saved_position = list(data['pos'])
        group.hide()
        group.reveal()
        assert group.isVisible() and data['pos'] == saved_position
        group.move(*saved_position)
        second = widget.Group(restored)
        assert second.pos() == group.pos() and len(second.data["tasks"]) == 4
        # 写入失败不能更改内存或磁盘中的任务。
        before = json.loads(Path(widget.DATA_FILE).read_text(encoding="utf-8"))
        with patch.object(widget, "save_data", return_value=False):
            assert group.add(today.isoformat(), "不应加入") is False
            group.remove(data["tasks"][0])
        assert data == before
        # 真正的原子写入失败也必须保留已有文件。
        good_path = widget.DATA_FILE
        with patch.object(widget, "DATA_FILE", folder), patch.object(widget.QMessageBox, "warning"):
            assert not widget.save_data(data)
        assert json.loads(Path(good_path).read_text(encoding="utf-8")) == before
        # 跨日刷新无需重启。
        group.today = today - timedelta(days=1)
        group.check_day()
        assert group.today == today
        for task in list(data["tasks"]):
            group.remove(task)
        QTest.qWait(100)
        assert group.isVisible() and group.plus.isVisible()
        group.grab().save(str(Path(__file__).with_name("preview-empty.png")))
        many = dict(data, tasks=[{"date": today.isoformat(), "title": str(i), "c": 0} for i in range(30)])
        overflow = widget.Group(many)
        overflow.show()
        QTest.qWait(100)
        assert overflow.scroll.verticalScrollBar().maximum() > 0
        overflow.scroll.verticalScrollBar().setValue(overflow.scroll.verticalScrollBar().maximum())
        assert overflow.plus.isVisible()
        overflow.close()
        Path(widget.DATA_FILE).write_text("broken json", encoding="utf-8")
        try:
            widget.load_data()
            raise AssertionError("损坏数据必须报错，不能静默重置")
        except json.JSONDecodeError:
            pass
        group.close()
        second.close()
    print("PASS: widget flows, editable examples, date sorting, persistence, data protection")


if __name__ == "__main__":
    check()
