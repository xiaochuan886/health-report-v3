# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path

project_root = Path.cwd()


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
    hiddenimports=[
        "pystray",
        "pystray._darwin",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="HealthReportWeb",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    name="HealthReportWeb",
)

app = BUNDLE(
    coll,
    name="HealthReportWeb.app",
    icon=None,
    bundle_identifier="com.local.healthreport.web",
)
