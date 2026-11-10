"""Generate the native icon from the existing cat drawing on macOS."""
from pathlib import Path
import subprocess
from PySide6.QtWidgets import QApplication
from main import make_icon

app = QApplication([])
folder = Path('build/CatCountdown.iconset')
folder.mkdir(parents=True, exist_ok=True)
for size in (16, 32, 128, 256, 512):
    for scale in (1, 2):
        pixels = size * scale
        suffix = '@2x' if scale == 2 else ''
        assert make_icon(pixels).pixmap(pixels, pixels).save(str(folder / f'icon_{size}x{size}{suffix}.png'))
subprocess.run(['iconutil', '-c', 'icns', str(folder), '-o', 'build/cat.icns'], check=True)
