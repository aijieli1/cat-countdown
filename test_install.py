"""Test install / first launch / upgrade / uninstall with isolated task data.
Run before installing this app for your own account. Uses the normal installer
registration temporarily; refuses to overwrite an existing installation.
"""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time
import winreg
from test_exe import wait_window

UNINSTALL_KEY = r'Software\Microsoft\Windows\CurrentVersion\Uninstall\{24B937C3-032A-4ECD-9824-A2643C79119E}_is1'


def check():
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, UNINSTALL_KEY):
            raise RuntimeError('Existing installation found; do not run this test against user installation.')
    except FileNotFoundError:
        pass
    setup = next((Path(__file__).parent / 'installer-output').glob('*.exe')).resolve()
    with tempfile.TemporaryDirectory(prefix='cat-countdown-install-') as folder:
        root = Path(folder)
        install = root / 'app'
        profile = root / 'profile'
        profile.mkdir()
        env = dict(os.environ, LOCALAPPDATA=str(profile))
        # Save and restore the autostart value because the uninstaller owns this value.
        run_key = r'Software\Microsoft\Windows\CurrentVersion\Run'
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, run_key) as key:
            try:
                startup = winreg.QueryValueEx(key, 'CountdownWidget')
            except FileNotFoundError:
                startup = None
        try:
            command = [str(setup), '/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART', '/NOICONS',
                       f'/DIR={install}', f'/LOG={root / "install.log"}']
            subprocess.run(command, check=True, env=env, timeout=120)
            exe = install / 'CountdownWidget.exe'
            assert exe.exists() and (install / '_internal/PySide6/Qt6Core.dll').exists()
            process = subprocess.Popen([str(exe)], env=env)
            wait_window('倒计时 · 猫猫待办', process.pid)
            datafile = profile / 'CountdownWidget/tasks.json'
            data = json.loads(datafile.read_text(encoding='utf-8'))
            assert len(data['tasks']) == 3 and all('示例' in t['title'] for t in data['tasks'])
            subprocess.run([str(exe), '--quit'], check=True, env=env, timeout=10)
            process.wait(timeout=10)
            assert datafile.exists()
            # Upgrade while running exercises the installer shutdown path.
            process = subprocess.Popen([str(exe)], env=env)
            wait_window('倒计时 · 猫猫待办', process.pid)
            subprocess.run(command, check=True, env=env, timeout=120)
            process.wait(timeout=10)
            assert json.loads(datafile.read_text(encoding='utf-8')) == data
            # Uninstall while running; data must survive.
            process = subprocess.Popen([str(exe)], env=env)
            wait_window('倒计时 · 猫猫待办', process.pid)
            subprocess.run([str(install / 'unins000.exe'), '/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART'],
                           check=True, env=env, timeout=120)
            process.wait(timeout=10)
            for _ in range(30):
                if not exe.exists():
                    break
                time.sleep(.1)
            assert not exe.exists() and datafile.exists()
            assert json.loads(datafile.read_text(encoding='utf-8')) == data
        finally:
            uninstaller = install / 'unins000.exe'
            if uninstaller.exists():
                subprocess.run([str(uninstaller), '/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART'], env=env, timeout=120)
            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, run_key) as key:
                if startup is not None:
                    winreg.SetValueEx(key, 'CountdownWidget', 0, startup[1], startup[0])
    print('PASS: install, first-launch three examples, graceful quit, running upgrade, uninstall, data preserved')


if __name__ == '__main__':
    check()
