# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['api_server.py'],
    pathex=[],
    binaries=[],
    datas=[('config.ini', '.'), ('knowledge_base', 'knowledge_base'), ('positions', 'positions'), ('learning_resources.json', '.'), ('interview_history.json', '.'), ('interview_history.db', '.'), ('baidu_ocr_token.json', '.'), ('assets', 'assets'), ('pages', 'pages'), ('index.html', '.'), ('login.html', '.')],
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
    name='InterviewApi',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='InterviewApi',
)
