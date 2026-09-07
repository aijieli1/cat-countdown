from pathlib import Path
import sys
import PySide6

a = Analysis(['main.py'], datas=[('licenses', 'licenses'), ('LICENSE', '.'),
                              ('THIRD_PARTY_NOTICES.md', '.'), ('README.md', '.')],
             binaries=[], hiddenimports=[], excludes=[])
qt = Path(PySide6.__file__).parent
a.binaries = [(dest, str(qt / Path(src).name), kind)
              if Path(src).name.lower() in ('vcruntime140.dll', 'vcruntime140_1.dll')
              else (dest, src, kind) for dest, src, kind in a.binaries]
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name='CountdownWidget',
          console=False, icon='cat.ico', upx=False)
coll = COLLECT(exe, a.binaries, a.datas, name='CountdownWidget', upx=False)
if sys.platform == 'darwin':
    app = BUNDLE(coll, name='CatCountdown.app', icon=None,
                 bundle_identifier='com.aijieli.catcountdown',
                 info_plist={'CFBundleShortVersionString': '1.0.0', 'LSUIElement': True})
