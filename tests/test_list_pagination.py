"""
Shared pager: First, Prev, the current page with two either side, Next, Last,
with every search and filter kept in the links. Also MCC collections show FAT / SNF.
"""

import re
from datetime import datetime
from decimal import Decimal
from uuid import uuid4

import pytest
from starlette.requests import Request

from app.modules.administration.domain.enums import Role
from app.modules.collections.mcc_collection.domain.enums import CollectionShift
from app.modules.collections.mcc_collection.infrastructure.models import MccCollectionModel
from app.modules.mcc.domain.enums import MccType
from app.modules.mcc.infrastructure.models import MccModel
from app.modules.ratechart.domain.enums import MilkType
from app.web.framework.pagination import page_numbers, page_url
from tests.dataexchange.factories import create_farmers, create_user, create_vlcc

HTML = {"accept": "text/html"}


@pytest.mark.parametrize(
    ("page", "total", "expected"),
    [
        (10, 20, [8, 9, 10, 11, 12]),
        (1, 20, [1, 2, 3, 4, 5]),
        (2, 20, [1, 2, 3, 4, 5]),
        (19, 20, [16, 17, 18, 19, 20]),
        (20, 20, [16, 17, 18, 19, 20]),
        (2, 3, [1, 2, 3]),
        (1, 1, [1]),
        (99, 20, [16, 17, 18, 19, 20]),
        (0, 20, [1, 2, 3, 4, 5]),
        (1, 0, []),
    ],
)
def test_page_numbers(page, total, expected):
    assert page_numbers(page, total) == expected


def _request(query: str) -> Request:
    return Request({"type": "http", "path": "/farmer", "query_string": query.encode(), "headers": []})


def test_page_url_keeps_every_filter_and_replaces_only_the_page():
    url = page_url(_request("search=Ram+Lal&page=3&vlcc_id=abc&limit=20"), 7)
    assert url.startswith("/farmer?") and url.endswith("page=7")
    assert "search=Ram+Lal" in url and "vlcc_id=abc" in url and "limit=20" in url and "page=3" not in url


def test_page_url_escapes_values():
    assert "search=%3Cb%3E%26x" in page_url(_request("search=%3Cb%3E%26x"), 2)


def _pager(page: str) -> str:
    return page.split('aria-label="Pages"')[1].split("</nav>")[0]


async def test_farmer_list_pager(api, database, token_for):
    admin = await create_user(database, role=Role.ADMIN)
    vlcc = await create_vlcc(database, created_by=admin)
    await create_farmers(database, vlcc, 20, prefix=f"G{uuid4().hex[:5]}")

    page = (await api.get("/farmer", params={"page": 10, "limit": 1, "vlcc_id": str(vlcc.id)}, headers=token_for(admin, Role.ADMIN) | HTML)).text
    pager = _pager(page)

    assert re.findall(r'class="page-num[^"]*"[^>]*>(\d+)<', pager) == ["8", "9", "10", "11", "12"]
    assert 'aria-current="page">10<' in pager
    for label, target in (("First", 1), ("Prev", 9), ("Next", 11), ("Last", 20)):
        link = re.search(rf'href="([^"]+)"[^>]*>[^<]*(?:<i[^>]*></i>)?\s*{label}', pager)
        assert link, label
        href = link.group(1).replace("&amp;", "&")
        assert href.endswith(f"page={target}") and f"vlcc_id={vlcc.id}" in href and "limit=1" in href


async def test_first_page_disables_first_and_prev(api, database, token_for):
    admin = await create_user(database, role=Role.ADMIN)
    vlcc = await create_vlcc(database, created_by=admin)
    await create_farmers(database, vlcc, 3, prefix=f"H{uuid4().hex[:5]}")

    pager = _pager((await api.get("/farmer", params={"limit": 1, "vlcc_id": str(vlcc.id)}, headers=token_for(admin, Role.ADMIN) | HTML)).text)

    assert 'btn-page disabled" aria-disabled="true"><i class="fa-solid fa-angles-left" aria-hidden="true"></i> First' in pager
    assert re.findall(r'class="page-num[^"]*"[^>]*>(\d+)<', pager) == ["1", "2", "3"]


@pytest.mark.parametrize(
    "url",
    ["/farmer", "/vlcc", "/mcc", "/ratecharts", "/vlcc-collections", "/mcc-collections", "/units", "/routes", "/items", "/sub-admins", "/recycle-bin", "/advance-items/", "/vlcc-dispatches"],
)
async def test_every_list_still_opens(api, database, token_for, url):
    admin = await create_user(database, role=Role.SUPER_ADMIN)
    response = await api.get(url, params={"page": 2}, headers=token_for(admin, Role.SUPER_ADMIN) | HTML, follow_redirects=True)
    assert response.status_code == 200, (url, response.status_code)
    assert "range(1, total_pages" not in response.text


async def test_mcc_collection_list_shows_fat_and_snf(api, database, token_for):
    admin = await create_user(database, role=Role.ADMIN)
    user_id = await create_user(database, role=Role.MCC, created_by=admin)
    mcc_id = uuid4()
    async with database.transaction() as session:
        session.add(MccModel(id=mcc_id, user_id=user_id, code=f"M{mcc_id.hex[:6]}", name="Hub", mcc_type=MccType.NORMAL, created_by=admin))
    vlcc = await create_vlcc(database, created_by=admin)
    async with database.transaction() as session:
        for fat, snf, milk in (("4.6", "8.7", MilkType.COW), ("0", "0", MilkType.MIXED)):
            session.add(MccCollectionModel(
                id=uuid4(), mcc_id=mcc_id, vlcc_id=vlcc.id, shift=CollectionShift.MORNING, milk_type=milk,
                quantity=Decimal("10"), fat_percent=Decimal(fat), snf_percent=Decimal(snf), collected_at=datetime(2026, 9, 1, 7),
            ))

    page = (await api.get("/mcc-collections", params={"mcc_id": str(mcc_id)}, headers=token_for(admin, Role.ADMIN) | HTML)).text

    assert "Milk Specs" in page
    assert re.search(r"FAT 4\.60% \S SNF 8\.70%", page), re.findall(r"FAT [^<]{0,30}", page)
    specs = re.findall(r"<!-- Milk Specs -->\s*<td[^>]*>(.*?)</td>", page, re.S)
    assert any(re.search(r">—</div>", cell) for cell in specs), specs
