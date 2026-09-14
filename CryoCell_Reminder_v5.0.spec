# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['CryoCell_Reminder_v5.0-CLEAN.py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'torch',
        'tensorflow',
        'keras',
        'transformers',
        'cv2',
        'sklearn',
        'scipy',
        'matplotlib',
        'IPython',
        'sympy',
        'h5py',
        # openpyxl 仅在处理工作簿图片时需要 Pillow；本应用不使用该能力。
        # 排除它可避免部分 Windows 环境解压 _imaging.pyd 失败。
        'PIL',
    ],
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
    name='CryoCell_Reminder_v5.13',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['cryo_cell_frozen.ico'],
)
