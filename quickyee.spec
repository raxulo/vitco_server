# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller build spec for Quickyee - produces ONE single-file executable.

Build:
    pyinstaller --clean --noconfirm quickyee.spec

Output:
    Linux  : dist/quickyee        (run: ./dist/quickyee)
    Windows: dist/quickyee.exe

Only Python source is packed into the binary; templates / static are bundled
inside it too, while .env, storage/ and logs/ stay next to the binary at runtime
(see _resolve_base_dir() in app/config/settings.py).
"""

from PyInstaller.utils.hooks import collect_submodules, collect_data_files

# ---- Non-code files that must travel inside the binary --------------------
# Jinja templates and static assets are resolved from app/web/__file__, which
# points inside the unpack dir at runtime, so they must keep the same layout.
datas = [
    ("app/web/templates", "app/web/templates"),
    ("app/web/static", "app/web/static"),
]
datas += collect_data_files("tzdata")  # ZoneInfo("Asia/Kolkata") needs the tz DB

# ---- Modules PyInstaller's static scan can miss ---------------------------
hiddenimports = []
hiddenimports += collect_submodules("app")       # every app.* module
hiddenimports += collect_submodules("uvicorn")   # loops / protocols / lifespan
hiddenimports += [
    "aiosqlite",
    "argon2",
    "_cffi_backend",
    "email_validator",
    "orjson",
    "msgspec",
    "PIL",
    "jose",
]

a = Analysis(
    ["run_server.py"],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure)

# Including a.binaries + a.datas in EXE (and no COLLECT) => a single file.
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="quickyee",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
