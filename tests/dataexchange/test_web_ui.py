"""
Web Panel Excel Exchange UI Tests (Plan 5.1, REQ-19).
Verifies cookie authentication for Excel API endpoints and modal integration in list templates.
"""

from __future__ import annotations

import pytest

from app.config.settings import settings
from app.modules.administration.domain.enums import Role
from app.modules.auth.infrastructure.jwt import JWTService
from tests.dataexchange.factories import create_user


def _token(user_id: str, role: Role = Role.ADMIN) -> str:
    jwt = JWTService(secret_key=settings.SECRET_KEY)
    return jwt.create_access_token(str(user_id), {"role": str(int(role)), "name": "Admin"})


async def test_cookie_auth_works_for_excel_api(api, database):
    """Browser cookie 'access_token' authenticates /api/v1/excel/ endpoints directly."""
    admin = await create_user(database, role=Role.ADMIN)
    token = _token(str(admin))

    # Request with cookies only, no Authorization header
    resp = await api.get("/api/v1/excel/farmers/options", cookies={"access_token": token})
    assert resp.status_code == 200
    assert resp.json()["status"] is True


async def test_farmer_list_contains_excel_buttons(api, database):
    """Farmer list page includes Excel export and import buttons triggering the modal."""
    admin = await create_user(database, role=Role.ADMIN)
    token = _token(str(admin))

    resp = await api.get("/farmer", cookies={"access_token": token})
    assert resp.status_code == 200
    html = resp.text
    assert "openExcelExchangeModal('farmers', 'export')" in html
    assert "openExcelExchangeModal('farmers', 'import')" in html
    assert "excel-exchange-modal" in html
    assert "excel_exchange.js" in html


async def test_vlcc_list_contains_excel_buttons(api, database):
    """VLCC list page includes Excel export and import buttons triggering the modal."""
    admin = await create_user(database, role=Role.ADMIN)
    token = _token(str(admin))

    resp = await api.get("/vlcc", cookies={"access_token": token})
    assert resp.status_code == 200
    html = resp.text
    assert "openExcelExchangeModal('vlccs', 'export')" in html
    assert "openExcelExchangeModal('vlccs', 'import')" in html
    assert "excel-exchange-modal" in html


async def test_ratechart_list_contains_prodata_buttons(api, database):
    """Rate charts list page includes Prodata export and import buttons triggering the modal."""
    admin = await create_user(database, role=Role.ADMIN)
    token = _token(str(admin))

    resp = await api.get("/ratecharts", cookies={"access_token": token})
    assert resp.status_code == 200
    html = resp.text
    assert "openExcelExchangeModal('prodata', 'export')" in html
    assert "openExcelExchangeModal('prodata', 'import')" in html
    assert "openExcelExchangeModal('formula', 'export')" in html
    assert "openExcelExchangeModal('formula', 'import')" in html
    assert "excel-exchange-modal" in html
