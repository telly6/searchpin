# -*- mode: python ; coding: utf-8 -*-
"""
MiniSearch PyInstaller spec — produces MiniSearch.app

To build a production release (smaller output, ~200MB):
    python3 -m venv /tmp/minisearch-build
    source /tmp/minisearch-build/bin/activate
    pip install fastembed numpy pyinstaller
    pyinstaller MiniSearch.spec
"""

import os

project_dir = os.path.dirname(os.path.abspath(SPECPATH))

a = Analysis(
    [os.path.join(project_dir, 'app.py')],
    pathex=[project_dir],
    binaries=[],
    datas=[
        (os.path.join(project_dir, 'search_engine.py'), '.'),
        (os.path.join(project_dir, 'search_server.py'), '.'),
    ],
    hiddenimports=[
        'tkinter',
        'tkinter.ttk',
        'tkinter.messagebox',
        'fastembed',
        'fastembed.text',
        'fastembed.text.text_embedding',
        'fastembed.text.onnx_embedding',
        'fastembed.common',
        'fastembed.common.model_management',
        'numpy',
        'http.server',
        'ssl',
        'threading',
        'concurrent.futures',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tensorflow', 'torch', 'keras', 'transformers', 'jax',
        'PIL', 'matplotlib', 'scipy', 'pandas',
    ],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='MiniSearch',
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
    icon=[os.path.join(project_dir, 'MiniSearch.icns')],
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='MiniSearch',
)

app = BUNDLE(
    coll,
    name='MiniSearch.app',
    icon=os.path.join(project_dir, 'MiniSearch.icns'),
    bundle_identifier='com.minisearch.app',
    info_plist={
        'CFBundleShortVersionString': '1.0.0',
        'CFBundleVersion': '1.0.0',
        'CFBundleName': 'MiniSearch',
        'CFBundleDisplayName': 'MiniSearch',
        'NSHighResolutionCapable': True,
        'NSHumanReadableCopyright': 'MiniSearch — self-hosted free search for AI agents',
        'LSMinimumSystemVersion': '12.0.0',
    },
)
