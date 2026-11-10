"""macOS packaged app check with Cocoa and an isolated user home."""
import json
import hashlib
import os
from pathlib import Path
import plistlib
import subprocess
import tempfile
import time
from unittest.mock import patch
import main
from PySide6.QtCore import QCoreApplication
from PySide6.QtNetwork import QLocalSocket

assert os.uname().sysname == 'Darwin'
bundle = Path('dist/CatCountdown.app').resolve()
with (bundle / 'Contents/Info.plist').open('rb') as stream:
    info = plistlib.load(stream)
assert (bundle / 'Contents/Resources' / info['CFBundleIconFile']).is_file()
exe = bundle / 'Contents/MacOS/CountdownWidget'
qt = QCoreApplication([])
with tempfile.TemporaryDirectory() as folder:
    # Verify the login configuration without changing this runner's login items.
    agent = Path(folder) / 'LaunchAgents/cat.plist'
    with patch.object(main, 'MAC_AUTOSTART', agent):
        assert main.set_autostart(True) and main.autostart_on()
        with agent.open('rb') as stream:
            payload = plistlib.load(stream)
        assert payload['RunAtLoad'] and payload['ProgramArguments']
        assert main.set_autostart(False) and not main.autostart_on()
    env = dict(os.environ, HOME=folder)
    env.pop('QT_QPA_PLATFORM', None)  # Exercise the packaged Cocoa app.
    datafile = Path(folder) / 'Library/Application Support/CountdownWidget/tasks.json'
    for attempt in range(2):
        with tempfile.TemporaryFile() as errors:
            proc = subprocess.Popen([str(exe)], env=env, stderr=errors)
            try:
                deadline = time.monotonic() + 30
                server = main.APP + hashlib.sha256(str(datafile.parent).encode()).hexdigest()[:16]
                probe = QLocalSocket()
                while proc.poll() is None and time.monotonic() < deadline:
                    probe.connectToServer(server)
                    if probe.waitForConnected(100):
                        break
                    probe.abort()
                    time.sleep(.1)
                assert probe.state() == QLocalSocket.ConnectedState, f'App IPC unavailable: {probe.errorString()}'
                probe.disconnectFromServer()
                assert datafile.exists() and proc.poll() is None, 'Packaged app failed to start'
                before = datafile.read_bytes()
                assert len(json.loads(before)['tasks']) == 3
                subprocess.run([str(exe), '--reveal'], env=env, timeout=15, check=True)
                subprocess.run([str(exe), '--quit'], env=env, timeout=15, check=True)
                assert proc.wait(timeout=15) == 0
                assert datafile.read_bytes() == before, 'Restart modified user tasks'
            finally:
                if proc.poll() is None:
                    proc.terminate()
                    proc.wait(timeout=10)
                errors.seek(0)
                log = errors.read().decode(errors='replace')
                print(log)
                assert 'Traceback' not in log
print('PASS: native Cocoa packaged startup, reopen IPC, quit, restart, data retention, icon, login config')
