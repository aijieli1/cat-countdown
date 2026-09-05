"""Windows 打包冒烟检查：临时数据启动 exe，验证全局快捷键和重启。"""
import ctypes
from ctypes import wintypes
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time
from unittest.mock import patch
import winreg
import main as widget

user32 = ctypes.windll.user32
user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
user32.IsWindowVisible.argtypes = [wintypes.HWND]
user32.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]


def windows(title, pid=None):
    found = []
    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def visit(hwnd, _):
        text = ctypes.create_unicode_buffer(256)
        user32.GetWindowTextW(hwnd, text, 256)
        owner = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(owner))
        if text.value == title and user32.IsWindowVisible(hwnd) and (pid is None or owner.value == pid):
            found.append(hwnd)
        return True
    user32.EnumWindows(visit, 0)
    return found


def wait_window(title, pid=None):
    deadline = time.monotonic() + 20
    while time.monotonic() < deadline:
        found = windows(title, pid)
        if found:
            return found[0]
        time.sleep(.1)
    raise AssertionError(f"窗口未出现: {title}")


def check():
    exe = Path(__file__).parent / "dist" / "CountdownWidget" / "CountdownWidget.exe"
    with tempfile.TemporaryDirectory() as folder:
        store = Path(folder) / "CountdownWidget"
        store.mkdir()
        data = {"tasks": [{"date": "2026-10-16", "title": "独立打包测试", "c": 0}], "pos": [100, 120], "seq": 1}
        datafile = store / "tasks.json"
        datafile.write_text(json.dumps(data), encoding="utf-8")
        env = dict(os.environ, LOCALAPPDATA=folder)
        for run in range(2):
            proc = subprocess.Popen([str(exe)], env=env)
            try:
                window = wait_window("倒计时 · 猫猫待办", proc.pid)
                if run == 0:
                    duplicate = subprocess.Popen([str(exe)], env=env)
                    try:
                        duplicate.wait(timeout=10)
                        time.sleep(.3)
                        assert len(windows("倒计时 · 猫猫待办")) == 1
                        assert not windows("倒计时")
                    finally:
                        if duplicate.poll() is None:
                            subprocess.run(["taskkill", "/PID", str(duplicate.pid), "/T", "/F"], capture_output=True)
                # 本执行环境拦截键盘注入；验证注册占用及原生 WM_HOTKEY 分发。
                assert not user32.RegisterHotKey(None, 0xC072, 0x4003, 0x54)
                thread = user32.GetWindowThreadProcessId(window, None)
                assert user32.PostThreadMessageW(thread, 0x0312, 0xC071, 0)
                popup = wait_window("添加倒计时", proc.pid)
                user32.PostMessageW(popup, 0x100, 0x1B, 0)
                time.sleep(.2)
                assert not windows("添加倒计时")
                assert json.loads(datafile.read_text(encoding="utf-8")) == data
            finally:
                subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"], capture_output=True)
                proc.wait(timeout=10)
                time.sleep(.5)
    # 在独立注册表值名上验证真实开启、查询、关闭，不修改用户原启动项。
    with patch.object(widget, "APP", "CountdownWidgetSmokeTest"), patch.object(widget, "autostart_cmd", return_value=f'"{exe}"'):
        try:
            assert widget.set_autostart(True) and widget.autostart_on()
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, widget.RUN_KEY) as key:
                assert winreg.QueryValueEx(key, widget.APP)[0] == f'"{exe}"'
            assert widget.set_autostart(False) and not widget.autostart_on()
        finally:
            widget.set_autostart(False)
    print("PASS: exe startup, hotkey registration/native dispatch, Escape, restart, unchanged JSON, autostart registration")


if __name__ == "__main__":
    check()
