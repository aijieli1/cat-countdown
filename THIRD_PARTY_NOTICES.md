# Third-party software

Application code and the cat illustration are MIT-licensed (see LICENSE).
Bundled dependencies remain under their own licenses. No ownership of those
dependencies is claimed by this project.

- **Python 3.12**: Python Software Foundation License. https://www.python.org/downloads/source/
- **Qt 6.8.3 / PySide6-Essentials 6.8.3 / Shiboken6 6.8.3**: distributed under the applicable LGPLv3 open-source terms. Full LGPLv3 and accompanying GPLv3 text are in licenses/. Upstream source: https://code.qt.io/cgit/qt/qtbase.git/tree/?h=v6.8.3 and https://code.qt.io/cgit/pyside/pyside-setup.git/tree/?h=v6.8.3 . These components are dynamically loaded from _internal and may be replaced with compatible modified versions; application source and build instructions are provided. Reverse engineering for debugging modifications to these LGPL components is permitted.
- **Qt third-party components**: copyright notices and licenses from the Qt 6.8.3 source tree are included in licenses/qt-third-party/ where applicable. Source and attributions: https://doc.qt.io/qt-6.8/licenses-used-in-qt.html .
- **PyInstaller bootloader 6.22.2**: GPLv2-or-later with a special exception permitting distribution of bundled applications under their own licenses. See licenses/PyInstaller-COPYING.txt and https://github.com/pyinstaller/pyinstaller/tree/v6.22.2 .
- **Inno Setup 6**: installer engine, copyright Jordan Russell and Martijn Laan; see licenses/Inno-Setup.txt and https://jrsoftware.org/isinfo.php . The Simplified Chinese installer translation is from the upstream Inno Setup repository; its original header is retained in ChineseSimplified.isl.

The public source, pinned dependencies, and independent dynamic libraries are
provided to make rebuilding and replacing the LGPL-covered components possible.
