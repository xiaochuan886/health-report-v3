# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec — HealthReportWeb（macOS .app 包模式）

入口 app_web_mvp.py：启动 macOS 状态栏托盘 + 后台 Web 服务。
构建产物：dist/HealthReportWeb.app
"""

import os
from PyInstaller.utils.hooks import collect_submodules

# 项目根目录（spec 文件位于 packaging/pyinstaller/ 下）
ROOT = os.path.abspath(os.path.join(SPECPATH, "..", ".."))
SRC = os.path.join(ROOT, "src")

# reportlab / pypdf 有大量动态导入的子模块，必须显式收集
hiddenimports = []
hiddenimports += collect_submodules("reportlab")
hiddenimports += collect_submodules("pypdf")
hiddenimports += [
    "pystray",
    "pystray._util",
    "pystray.Darwin",      # macOS 托盘后端
    "PIL._tkinter_finder",
]

# report_pipeline 包的数据资源（health_guide、images、fonts、logo）
datas = [
    (os.path.join(SRC, "report_pipeline", "data"), "report_pipeline/data"),
    (os.path.join(SRC, "report_pipeline", "fonts"), "report_pipeline/fonts"),
    (os.path.join(SRC, "report_pipeline", "logo.png"), "report_pipeline"),
    (os.path.join(SRC, "report_pipeline", "logo.svg"), "report_pipeline"),
]

# 减小体积：排除不需要的大包
excludes = [
    "matplotlib",
    "scipy",
    "numpy.testing",
    "pytest",
    "IPython",
    "notebook",
    "jupyter",
]

block_cipher = None

a = Analysis(
    [os.path.join(ROOT, "app_web_mvp.py")],
    pathex=[SRC],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="HealthReportWeb",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,  # .app 模式不显示控制台
    disable_windowed_traceback=False,
    icon=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="HealthReportWeb",
)

app = BUNDLE(
    coll,
    name="HealthReportWeb.app",
    bundle_identifier="com.healthreport.web",
    info_plist={
        "CFBundleDisplayName": "综合健康报告",
        "CFBundleShortVersionString": "3.0.0",
        "CFBundleName": "HealthReportWeb",
        "NSHighResolutionCapable": True,
        "LSMinimumSystemVersion": "10.13",
    },
)
