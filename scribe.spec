# -*- mode: python ; coding: utf-8 -*-

import os as _spec_os
from PyInstaller.building.datastruct import TOC
from PyInstaller.utils.hooks import collect_data_files, copy_metadata

# pymorphy2 finds dictionaries via pkg_resources entry points, which need
# dist-info metadata, plus the data dirs themselves.
_pymorphy_datas = (
    collect_data_files('pymorphy2_dicts_ru')
    + collect_data_files('pymorphy2_dicts_uk')
    + copy_metadata('pymorphy2-dicts-ru')
    + copy_metadata('pymorphy2-dicts-uk')
    + copy_metadata('pymorphy2')
)

# Qt ships stale MSVC runtimes (14.26) that shadow the fresh ones process-wide:
# whichever msvcp loads first wins, and onnxruntime needs the new CRT exports.
# CRT is backward compatible, so Qt runs fine on the fresh bundled copy.
_STALE_CRT = {'msvcp140.dll', 'msvcp140_1.dll', 'msvcp140_2.dll',
              'vcruntime140.dll', 'vcruntime140_1.dll', 'concrt140.dll'}

a = Analysis(
    ['run.py'],
    pathex=[],
    # Pin exact MSVC runtime versions (14.50): PyInstaller auto-collects stale
    # 14.29 copies from the build Python, while onnxruntime needs the new CRT.
    # Explicit entries win over auto-collected ones (first occurrence kept).
    binaries=[('venv/Lib/site-packages/onnxruntime/capi/onnxruntime.dll', '.'),
              ('venv/Lib/site-packages/onnxruntime/capi/onnxruntime_providers_shared.dll', '.'),
              ('C:/Windows/System32/vcruntime140.dll', '.'),
              ('C:/Windows/System32/vcruntime140_1.dll', '.'),
              ('C:/Windows/System32/msvcp140.dll', '.'),
              ('C:/Windows/System32/msvcp140_1.dll', '.')],
    datas=[('resources', 'resources'), ('translations', 'translations'), ('venv/Lib/site-packages/vosk', 'vosk')]
    + _pymorphy_datas,
    hiddenimports=['pymorphy2_dicts_ru', 'pymorphy2_dicts_uk'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    onefile=True,
    optimize=0,
)
pyz = PYZ(a.pure)

# Drop Qt-bundled stale CRT so nothing can load it before our pinned copy.
a.binaries = TOC([
    x for x in a.binaries
    if not (x[0].lower().replace('/', '\\').startswith('pyqt5\\qt5\\bin\\')
            and _spec_os.path.basename(x[0]).lower() in _STALE_CRT)
])

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='Scribe',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    # UPX corrupts onnxruntime native DLLs (DLL load failure at startup).
    upx_exclude=['onnxruntime*.dll', 'onnxruntime*.pyd', 'libiomp*.dll', 'mkl_*.dll'],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='resources\\icon.ico',
    version='file_version_info.txt'
)
