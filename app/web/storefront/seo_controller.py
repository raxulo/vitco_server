"""
robots.txt and sitemap.xml.

Python 3.13+
"""

from __future__ import annotations

from datetime import datetime
from xml.sax.saxutils import escape

from fastapi import APIRouter, Request
from starlette.responses import PlainTextResponse, Response

from app.modules.dependencies import GetHandler
from app.web.storefront.seo import store_url

router = APIRouter(tags=["Web Store"], include_in_schema=False)

_CACHE = "public, max-age=3600"
_POLICY_KEYS = ("shipping", "returns", "terms", "privacy")


@router.get("/robots.txt")
async def robots(request: Request) -> Response:
    # Everything else on this host is the management system, so only the store is opened to crawlers.
    lines = [
        "User-agent: *",
        "Allow: /marketplace",
        "Allow: /static/",
        "Allow: /api/v1/media/",
        "Allow: /api/v1/files/",
        "Disallow: /marketplace/cart",
        "Disallow: /marketplace/checkout",
        "Disallow: /marketplace/order-placed/",
        "Disallow: /",
        "",
        f"Sitemap: {store_url(request, '/sitemap.xml')}",
        "",
    ]
    return PlainTextResponse("\n".join(lines), headers={"Cache-Control": _CACHE})


def _entry(url: str, updated_at: datetime | None = None) -> str:
    modified = f"<lastmod>{updated_at.date().isoformat()}</lastmod>" if updated_at else ""
    return f"<url><loc>{escape(url)}</loc>{modified}</url>"


@router.get("/sitemap.xml")
async def sitemap(request: Request) -> Response:
    handler = GetHandler.storefront_handler(request)
    frame = await handler.frame()
    products, animals, category_slugs = await handler.sitemap()

    entries = [_entry(store_url(request, path)) for path in ("/marketplace", "/marketplace/products", "/marketplace/animals")]
    entries += [_entry(store_url(request, "/marketplace/products", category=slug)) for slug in category_slugs]
    entries += [_entry(store_url(request, "/marketplace/animals", type=row.slug)) for row in frame.animal_types]
    entries += [
        _entry(store_url(request, f"/marketplace/policies/{key}"))
        for key in _POLICY_KEYS if frame.settings.policies.get(key)
    ]
    entries += [_entry(store_url(request, f"/marketplace/products/{row.slug}"), row.updated_at) for row in products]
    entries += [_entry(store_url(request, f"/marketplace/animals/{row.slug}"), row.updated_at) for row in animals]

    body = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
        + "".join(entries)
        + "</urlset>\n"
    )
    return Response(body, media_type="application/xml", headers={"Cache-Control": _CACHE})
