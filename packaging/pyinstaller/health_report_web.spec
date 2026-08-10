# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path

# PyInstaller executes .spec without __file__; cwd is repo root in our build scripts.
project_root = Path.cwd()
block_cipher = None


a = Analysis(
    [str(project_root / "app_web_mvp.py")],
    pathex=[str(project_root / "src")],
    binaries=[],
    datas=[
        (str(project_root / "src" / "report_pipeline" / "data"), "report_pipeline/data"),
        (str(project_root / "src" / "report_pipeline" / "fonts"), "report_pipeline/fonts"),
        (str(project_root / "src" / "report_pipeline" / "logo.png"), "report_pipeline"),
        (str(project_root / "src" / "report_pipeline" / "logo.svg"), "report_pipeline"),
    ],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="HealthReportWeb",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
