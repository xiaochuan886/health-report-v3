# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec — HealthReportWeb（Windows / Linux 通用，单文件夹模式）

入口 app_web_mvp.py：macOS 优先启动托盘，其它平台降级为纯 Web 服务。
构建产物：dist/HealthReportWeb/（可执行文件 + 依赖目录）
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
    "pystray.Win32",       # Windows 托盘后端
    "pystray.Darwin",      # macOS 托盘后端（同一 spec 兼容）
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
    console=True,  # 保留控制台窗口便于排错；正式分发可改 False
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
