# Phase 15 Research: Public API, SEO & Launch Hardening

## API pattern
`app/api/v1/routers/unit_master.py` is the model: a local `_compute_pagination`, the standard list and single-record envelopes, `JSONResponse`. Domain errors reach `application_exception_handler`, which answers `/api` paths as JSON.

## Rate limits
- The server is one process (`run_server.py`: `workers=1`), so an in-memory counter sees every request. Nothing new is needed, such as Redis.
- `request.client.host` is the visitor only when Uvicorn trusts the proxy in front of it. Uvicorn trusts `127.0.0.1` by default, so a proxy on another machine needs `--forwarded-allow-ips`. This goes on the release checklist.
- Limits have to be generous, because villages on mobile networks share one IP.

## SEO
- `request.base_url` follows the `Host` header, and `TrustedHostMiddleware` allows any host. Links for search engines therefore need a setting for the real address, falling back to the request.
- The host also serves the management system, so `robots.txt` allows the store and refuses everything else.

## Packaging
`quickyee.spec` uses `collect_submodules("app")` and bundles templates and static files. New modules and pages are packaged without changes.
