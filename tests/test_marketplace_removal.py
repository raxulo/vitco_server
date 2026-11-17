"""
Phase 8: the old marketplace is gone (REQ-28) and startup leaves its tables alone (REQ-29).
"""

import importlib.util
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.api.v1.router import api_v1_router
from app.core.database.base import Base
from app.middleware.authentication import AuthenticationMiddleware
from app.modules.administration.domain.enums import Role
from app.modules.auth.infrastructure.jwt import JWTService
from app.modules.dashboard.presentation.navigation import build_navigation
from app.web.router import WebRouterRegistrar

TEMPLATES = Path("app/web/templates")
STATIC_JS = Path("app/web/static/js")


@pytest.fixture
def web_app() -> FastAPI:
    app = FastAPI()
    WebRouterRegistrar.register(app)
    app.include_router(api_v1_router, prefix="/api/v1")
    return app


def test_no_marketplace_route_is_registered(web_app):
    paths = list(web_app.openapi()["paths"])
    assert "/" in paths  # the walk really saw the web routes
    assert "/api/v1/auth/login" in paths  # and the API routes
    old = (
        "/marketplace/setup", "/marketplace/detail", "/marketplace/order/",
        "/api/v1/marketplace/banners", "/api/v1/marketplace/trending-tags", "/api/v1/marketplace/detail",
    )
    assert [path for path in paths if path.startswith(old)] == []


def test_old_modules_cannot_be_imported():
    assert importlib.util.find_spec("app.web.marketplace") is None


def test_no_model_maps_a_legacy_table():
    legacy = {"animals", "animal_types", "product_categories", "product_offers", "product_variants",
              "product_inventory", "marketplace_products", "marketplace_orders", "marketplace_banners"}
    assert legacy & set(Base.metadata.tables) == set()


@pytest.mark.parametrize("role", [role for role in Role if role != Role.SUPPORT])
def test_navigation_has_no_marketplace_link(role):
    urls = [menu.href for group in build_navigation(role.value) for menu in group.items]
    assert urls  # every dairy role still gets a menu
    assert [url for url in urls if url.startswith("/marketplace/")] == []  # old pages such as /marketplace/setup


def test_support_staff_get_no_dairy_menu():
    # Technical Support staff use their own portal and sidebar (REQ-58)
    assert build_navigation(Role.SUPPORT.value) == ()


def test_no_template_or_script_uses_the_old_cart_or_pages():
    files = [*TEMPLATES.rglob("*.html"), *STATIC_JS.glob("*.js")]
    assert files
    for path in files:
        source = path.read_text(encoding="utf-8", errors="ignore")
        for leftover in ("toggleCartDrawer", "cart_drawer", "cart-badge-count", "/marketplace/setup", "/marketplace/detail"):
            assert leftover not in source, f"{leftover} left in {path}"


async def test_create_all_keeps_legacy_tables_and_rows(database):
    row_id = uuid4().hex
    async with database.transaction() as session:
        await session.execute(text("CREATE TABLE marketplace_banners (id CHAR(32) PRIMARY KEY)"))
        await session.execute(text("INSERT INTO marketplace_banners (id) VALUES (:id)"), {"id": row_id})
    try:
        assert "marketplace_banners" not in Base.metadata.tables

        async with database.transaction() as session:
            await session.run_sync(lambda sync: Base.metadata.create_all(sync.connection()))
            stored = await session.scalar(text("SELECT id FROM marketplace_banners"))
        assert stored == row_id
    finally:
        async with database.transaction() as session:
            await session.execute(text("DROP TABLE marketplace_banners"))


class TestRootAndOldUrls:
    """Runs the real auth middleware around the real web routes."""

    SECRET = "test-secret-key-for-marketplace-removal-tests"

    @pytest.fixture
    def client(self, web_app) -> TestClient:
        web_app.add_middleware(
            AuthenticationMiddleware,
            jwt_service=JWTService(secret_key=self.SECRET),
            public_routes={"/"},
        )
        return TestClient(web_app, follow_redirects=False)

    def test_guest_on_root_goes_to_the_store(self, client):
        response = client.get("/", headers={"accept": "text/html"})
        assert response.status_code == 302
        assert response.headers["location"] == "/marketplace"

    def test_old_order_list_is_not_served_any_more(self, client):
        # Only placing an order remains here; nobody can read the list of orders
        assert client.get("/api/v1/marketplace/orders").status_code == 405

    @pytest.fixture
    def logged_in_client(self, web_app) -> TestClient:
        @web_app.middleware("http")
        async def logged_in(request, call_next):
            request.state.user = object()
            return await call_next(request)

        return TestClient(web_app, follow_redirects=False)

    def test_logged_in_user_on_root_goes_to_dashboard(self, logged_in_client):
        response = logged_in_client.get("/")
        assert response.status_code == 302
        assert response.headers["location"] == "/dashboard"

    @pytest.mark.parametrize(
        "url", ["/marketplace/setup", "/marketplace/detail/animal/1", "/api/v1/marketplace/banners"]
    )
    def test_old_urls_are_gone_for_logged_in_users(self, logged_in_client, url):
        assert logged_in_client.get(url).status_code == 404
