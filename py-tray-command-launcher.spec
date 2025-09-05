# -*- mode: python ; coding: utf-8 -*-
import os

# Define paths
project_root = os.path.abspath('.')
src_path = os.path.join(project_root, 'src')

a = Analysis(
    ['src/main.py'],
    pathex=[src_path],
    binaries=[],
    datas=[
        ('config', 'config'),
        ('resources', 'resources'),
    ],
    hiddenimports=[
        'PyQt6.QtCore',
        'PyQt6.QtWidgets',
        'PyQt6.QtGui',
        'cryptography',
    ],
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
    a.binaries,
    a.datas,
    [],
    name='py-tray-command-launcher',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='resources/icons/icon.png' if os.path.exists('resources/icons/icon.png') else None,
)
