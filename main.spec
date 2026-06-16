# -*- mode: python ; coding: utf-8 -*-
# Trading Journal Pro – PyInstaller spec (onefile)
# Bundles: config.json, app_icon.ico
# Note: trading_data.json is NOT bundled – it lives next to the .exe at runtime.

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('config.json', '.'),       # Bundle default config inside the EXE
        ('app_icon.ico', '.'),      # Bundle icon
    ],
    hiddenimports=[
        'ib_insync',
        'ib_insync.ib',
        'ib_insync.client',
        'ib_insync.contract',
        'ib_insync.objects',
        'ib_insync.wrapper',
        'ib_insync.decoder',
        'ib_insync.util',
        'asyncio',
        'nest_asyncio',
        'eventkit',
        'ib_controller',
        'ib_client',
        'ib_exceptions',
        'account_panel',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tests',
        'pytest',
        'unittest',
        '_pytest',
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
    name='TradingJournalPro',
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
    icon=['app_icon.ico'],
)
