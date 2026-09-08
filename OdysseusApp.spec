# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['launcher_docker.py'],
    pathex=[],
    binaries=[],
    datas=[('C:/Users/aryan/OneDrive/Desktop/odysseus/static/icon.ico', 'static'), ('C:/Users/aryan/OneDrive/Desktop/odysseus/static/icon.png', 'static')],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='OdysseusApp',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['C:/Users/aryan/OneDrive/Desktop/odysseus/static/icon.ico'],
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='OdysseusApp',
)
