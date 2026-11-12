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
    # Alembic reads migration scripts from disk, not from the import system
    ("app/core/database/migrations", "app/core/database/migrations"),
]
datas += collect_data_files("tzdata")  # ZoneInfo("Asia/Kolkata") needs the tz DB
datas += collect_data_files("alembic")  # script templates Alembic loads at runtime

# ---- Modules PyInstaller's static scan can miss ---------------------------
hiddenimports = []
# Every app.* module, except the migration scripts: they only run inside Alembic
hiddenimports += collect_submodules("app", filter=lambda name: ".database.migrations" not in name)
hiddenimports += collect_submodules("uvicorn")   # loops / protocols / lifespan
hiddenimports += collect_submodules("asyncpg")   # PostgreSQL driver (default)
hiddenimports += collect_submodules("alembic")   # migrations run at startup
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
