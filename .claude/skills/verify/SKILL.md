---
name: verify
description: How to launch and drive the Quickyee API (and its Excel exchange worker) in isolation to verify a change at runtime
---

# Verifying Quickyee at runtime

## Launch an isolated server (never touch the real dev DB)
Override the settings through environment variables. They beat `.env`, which holds secrets you should not need to read:

```powershell
$dir = "<scratch dir>"; New-Item -ItemType Directory -Force "$dir\reload" | Out-Null
$env:DATABASE_URL = "sqlite+aiosqlite:///" + ($dir -replace '\\','/') + "/verify.db"
$env:EXCHANGE_PATH = "$dir\exchange"; $env:LOG_PATH = "$dir\logs"
$env:ADMIN_EMAIL = "verify.admin@example.com"; $env:ADMIN_PASSWORD = "Verify@12345"; $env:ADMIN_NAME = "Verify Admin"
Start-Process .\.venv\Scripts\uvicorn.exe -ArgumentList "app.main:app","--host","127.0.0.1","--port","5601" `
  -NoNewWindow -PassThru -RedirectStandardOutput "$dir\api.out" -RedirectStandardError "$dir\api.err"
# poll http://127.0.0.1:5601/healthz until 200
```

- `.claude/launch.json` uses `--reload`. To test reload, add `--reload-dir "$dir\reload"` and touch a `.py` file there instead of a repo file.
- Run uvicorn in its own console (`cmd /c run.cmd` with `Start-Process -WindowStyle Minimized`) when testing reload. On Windows uvicorn reloads with `CTRL_C_EVENT`, which also hits a shell that shares the console and can kill your driving script.

## Get a token
- Management users (Super Admin / Admin) cannot use `POST /api/v1/auth/login`; it is for MCC / VLCC / farmers.
- Use the web login instead: `POST /auth/login` with form `email`, `password` and header `HX-Request: true`. The response sets the cookie `access_token="Bearer <jwt>"`.
- Send `Authorization: Bearer <jwt>` to `/api/...`. Cookies are ignored on `/api` paths unless the request is HTMX.
- Mobile-app login (VLCC / MCC / farmer): `POST /api/v1/auth/login` with JSON `{"email": …}` or `{"mobile": …}` plus `"password"`. `identifier` is a computed property, not a request field; sending it fails with `AUTH_INVALID_CREDENTIALS`. The token is at `response["token"]["access_token"]`.
- To get a VLCC user in the isolated DB, insert a `users` row (role `VLCC`, `password_hash` from `PasswordService().hash(...)`) and a `vlcc_master` row with `farmer_enabled=1`. Ids are 32-char hex, enums are stored by name.

## Excel exchange (Phase 1+)
- Worker processes: `Get-CimInstance Win32_Process` with a CommandLine like `*app.worker.exchange*`. The `--parent-pid` value is the uvicorn server child, which is the `spawn_main` process under the reloader.
- With a venv on Windows, each worker shows as two processes, the launcher plus the real interpreter. Jobs record the real interpreter's PID.
- Farmers (Phase 2): `GET /api/v1/excel/options/vlccs` → `POST /api/v1/excel/uploads` + `PUT …/chunks/{n}` + `POST …/complete` (or `POST /uploads/single`) → `POST /api/v1/excel/farmers/import {"upload_id"}` / `POST /api/v1/excel/farmers/export {}` → poll `GET /api/v1/excel/jobs/{id}` until `poll_after_ms` is null → `GET …/file`.
- For other kinds without a submit endpoint yet, queue a job by inserting into `excel_jobs`.
- Teardown: kill the `spawn_main` server child too. Workers exit within about 2 s of their parent dying.
- Confirm the real DB is untouched: open `storage/database/realtime_transfer.db` read-only (`?mode=ro`).
