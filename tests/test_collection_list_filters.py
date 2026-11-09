"""
Collection list totals and filters: totals cover every matching entry, stay inside
the user's scope and leave out deleted entries; shifts work with dates as one range.
"""

import re
from datetime import date, datetime
from decimal import Decimal
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select, update

from app.modules.administration.domain.enums import Role
from app.modules.administration.infrastructure.models import UserModel
from app.modules.common.settings.infrastructure.models import SettingsModel
from app.modules.collections.mcc_collection.domain.enums import CollectionShift
from app.modules.collections.mcc_collection.domain.listing import CollectionPeriod
from app.core.numeric import fixed
from app.modules.collections.mcc_collection.infrastructure.listing_sql import totals_from_row
from app.modules.collections.mcc_collection.infrastructure.models import MccCollectionModel
from app.modules.collections.vlcc_collection.infrastructure.models import VlccCollectionModel
from app.modules.farmer.infrastructure.models import FarmerModel
from app.modules.mcc.domain.enums import MccType
from app.modules.mcc.infrastructure.models import MccModel
from app.modules.ratechart.domain.enums import MilkType
from app.modules.vlcc.infrastructure.models import VlccModel
from app.web.framework.collection_list import parse_period
from tests.dataexchange.factories import create_farmers, create_user, create_vlcc

VLCC_URL = "/vlcc-collections"
MCC_URL = "/mcc-collections"
HTML = {"accept": "text/html"}
MORNING, EVENING = CollectionShift.MORNING, CollectionShift.EVENING


def _totals(page: str) -> dict[str, str]:
    """The five figures exactly as the page shows them."""
    section = page.split('class="cl-totals"')[1].split("</section>")[0]
    pairs = re.findall(r'cl-total-label">([^<]+)</div>\s*<div class="cl-total-value[^"]*">([^<]+)<', section)
    return dict(pairs)


def _rows(page: str) -> int:
    return page.count('class="row-check"')


@pytest.fixture
async def admin(database):
    return await create_user(database, role=Role.ADMIN)


@pytest.fixture
def headers(token_for, admin):
    return token_for(admin, Role.ADMIN) | HTML


async def _offerable(database, vlcc) -> None:
    """The VLCC list, which fills the filter, only returns VLCCs that have settings."""
    settings_id = uuid4()
    async with database.transaction() as session:
        session.add(SettingsModel(id=settings_id))
        await session.flush()
        await session.execute(update(VlccModel).where(VlccModel.id == vlcc.id).values(settings_id=settings_id))


async def _farmers(database, vlcc, count: int, prefix: str) -> list[tuple[UUID, str, str]]:
    await create_farmers(database, vlcc, count, prefix=prefix)
    async with database.transaction() as session:
        rows = await session.execute(
            select(FarmerModel.id, FarmerModel.farmer_code, UserModel.name)
            .join(UserModel, UserModel.id == FarmerModel.user_id)
            .where(FarmerModel.vlcc_id == vlcc.id)
            .order_by(FarmerModel.farmer_code)
        )
        return [tuple(row) for row in rows]


async def _farmer_entry(database, vlcc, farmer_id, when, shift=MORNING, milk=MilkType.COW, quantity="10", fat="4", snf="8", amount="100", deleted=False):
    async with database.transaction() as session:
        session.add(VlccCollectionModel(
            id=uuid4(), vlcc_id=vlcc.id, farmer_id=farmer_id, milk_type=milk, shift=shift, collected_at=when,
            quantity=Decimal(quantity), fat_percent=Decimal(fat), snf_percent=Decimal(snf), rate_per_unit=Decimal("10"),
            total_amount=Decimal(amount), is_deleted=deleted,
        ))


async def _mcc(database, created_by: UUID, name: str) -> UUID:
    user_id = await create_user(database, role=Role.MCC, created_by=created_by)
    mcc_id = uuid4()
    async with database.transaction() as session:
        session.add(MccModel(id=mcc_id, user_id=user_id, code=f"M{mcc_id.hex[:6]}", name=name, mcc_type=MccType.NORMAL, created_by=created_by))
    return mcc_id


async def _mcc_entry(database, mcc_id, vlcc, when, shift=MORNING, milk=MilkType.COW, quantity="10", fat="4", snf="8", amount="100", deleted=False):
    async with database.transaction() as session:
        session.add(MccCollectionModel(
            id=uuid4(), mcc_id=mcc_id, vlcc_id=vlcc.id, milk_type=milk, shift=shift, collected_at=when,
            quantity=Decimal(quantity), fat_percent=Decimal(fat), snf_percent=Decimal(snf), rate_per_unit=Decimal("10"),
            total_amount=Decimal(amount), is_deleted=deleted,
        ))


# =========================================================
# VLCC COLLECTIONS
# =========================================================


async def test_totals_cover_every_page_and_are_weighted(api, database, admin, headers):
    vlcc = await create_vlcc(database, created_by=admin)
    (farmer, *_), = await _farmers(database, vlcc, 1, f"T{uuid4().hex[:5]}")
    await _farmer_entry(database, vlcc, farmer, datetime(2026, 1, 1, 7), quantity="10", fat="4", snf="8", amount="100.25")
    await _farmer_entry(database, vlcc, farmer, datetime(2026, 1, 2, 7), quantity="30", fat="6", snf="9", amount="300.50")
    await _farmer_entry(database, vlcc, farmer, datetime(2026, 1, 3, 7), quantity="1000", fat="9", snf="9", amount="9000", deleted=True)

    page = (await api.get(VLCC_URL, params={"vlcc_id": str(vlcc.id), "limit": 1}, headers=headers)).text

    assert _totals(page) == {
        "Total Qty (KG)": "40.00",
        "Total Amount": "₹400.75",
        "Avg. FAT": "5.50%",  # (10x4 + 30x6) / 40, not (4 + 6) / 2
        "Avg. SNF": "8.75%",
        "Total Entries": "2",
    }
    assert "1 deleted, not counted" in page


async def test_filters_change_rows_and_totals_together(api, database, admin, headers):
    tag = uuid4().hex[:5]
    shop_a = await create_vlcc(database, created_by=admin)
    shop_b = await create_vlcc(database, created_by=admin)
    farmers = await _farmers(database, shop_a, 2, f"A{tag}")
    other, = await _farmers(database, shop_b, 1, f"B{tag}")
    day = datetime(2026, 2, 1, 7)
    await _farmer_entry(database, shop_a, farmers[0][0], day, milk=MilkType.COW, quantity="1")
    await _farmer_entry(database, shop_a, farmers[1][0], day, milk=MilkType.BUFFALO, quantity="2")
    await _farmer_entry(database, shop_b, other[0], day, milk=MilkType.COW, quantity="4")

    async def check(expected_rows: int, expected_quantity: str, **params) -> None:
        page = (await api.get(VLCC_URL, params={"date_from": "2026-02-01", "date_to": "2026-02-01", **params}, headers=headers)).text
        assert _rows(page) == expected_rows, params
        assert _totals(page)["Total Qty (KG)"] == expected_quantity, params

    await check(1, "1.00", search=farmers[0][1])  # farmer code
    await check(1, "4.00", search=other[2])  # farmer name
    await check(2, "3.00", vlcc_id=str(shop_a.id))
    await check(1, "2.00", vlcc_id=str(shop_a.id), milk_type="1")
    await check(2, "5.00", milk_type="0", search=tag)


async def test_farmer_search_does_not_match_the_vlcc_name(api, database, admin, headers):
    tag = uuid4().hex[:8]
    vlcc = await create_vlcc(database, created_by=admin)
    (farmer, *_), = await _farmers(database, vlcc, 1, f"N{tag[:5]}")
    async with database.transaction() as session:
        await session.execute(update(VlccModel).where(VlccModel.id == vlcc.id).values(name=f"Gokul {tag}"))
    await _farmer_entry(database, vlcc, farmer, datetime(2026, 2, 2, 7))

    page = (await api.get(VLCC_URL, params={"search": f"Gokul {tag}"}, headers=headers)).text

    assert _rows(page) == 0 and _totals(page)["Total Entries"] == "0"


@pytest.mark.parametrize(
    ("params", "expected"),
    [
        # Entries: 1 Mar M=1, E=2; 2 Mar M=4, E=8; 3 Mar M=16, E=32
        ({"date_from": "2026-03-01", "date_to": "2026-03-03"}, "63.00"),
        ({"date_from": "2026-03-01", "date_to": "2026-03-03", "start_shift": "1"}, "62.00"),
        ({"date_from": "2026-03-01", "date_to": "2026-03-03", "end_shift": "0"}, "31.00"),
        ({"date_from": "2026-03-01", "date_to": "2026-03-03", "start_shift": "1", "end_shift": "0"}, "30.00"),
        ({"date_from": "2026-03-02", "date_to": "2026-03-02", "start_shift": "0", "end_shift": "0"}, "4.00"),
        ({"date_from": "2026-03-02", "date_to": "2026-03-02", "start_shift": "1", "end_shift": "1"}, "8.00"),
        # Entered the wrong way round
        # Each shift stays with its date: this reads as 1 Mar evening to 3 Mar morning
        ({"date_from": "2026-03-03", "date_to": "2026-03-01", "start_shift": "0", "end_shift": "1"}, "30.00"),
        ({"date_from": "2026-03-02", "date_to": "2026-03-02", "start_shift": "1", "end_shift": "0"}, "12.00"),
        # A shift without its date means that shift only
        ({"start_shift": "0"}, "21.00"),
        ({"end_shift": "1"}, "42.00"),
        ({"start_shift": "1", "end_shift": "1"}, "42.00"),
        ({"start_shift": "1", "end_shift": "0"}, "63.00"),
    ],
)
async def test_shift_range(api, database, admin, headers, params, expected):
    vlcc = await create_vlcc(database, created_by=admin)
    (farmer, *_), = await _farmers(database, vlcc, 1, f"S{uuid4().hex[:5]}")
    quantity = 1
    for day in (1, 2, 3):
        for shift, hour in ((MORNING, 7), (EVENING, 18)):
            await _farmer_entry(database, vlcc, farmer, datetime(2026, 3, day, hour), shift=shift, quantity=str(quantity))
            quantity *= 2

    page = (await api.get(VLCC_URL, params={"vlcc_id": str(vlcc.id), **params}, headers=headers)).text

    assert _totals(page)["Total Qty (KG)"] == expected


async def test_totals_stay_inside_the_users_scope(api, database, admin, headers, token_for):
    mine = await create_vlcc(database, created_by=admin)
    someone_else = await create_user(database, role=Role.ADMIN)
    theirs = await create_vlcc(database, created_by=someone_else)
    await _offerable(database, mine)
    await _offerable(database, theirs)
    (my_farmer, *_), = await _farmers(database, mine, 1, f"M{uuid4().hex[:5]}")
    (their_farmer, *_), = await _farmers(database, theirs, 1, f"O{uuid4().hex[:5]}")
    await _farmer_entry(database, mine, my_farmer, datetime(2026, 4, 1, 7), quantity="5")
    await _farmer_entry(database, theirs, their_farmer, datetime(2026, 4, 1, 7), quantity="500")

    everything = (await api.get(VLCC_URL, headers=headers)).text
    assert _totals(everything)["Total Qty (KG)"] == "5.00"
    assert f'value="{mine.id}"' in everything  # the filter offers this user's VLCC
    assert str(theirs.id) not in everything  # and not the other Admin's

    # Asking for the other Admin's VLCC by hand finds nothing
    asked = (await api.get(VLCC_URL, params={"vlcc_id": str(theirs.id)}, headers=headers)).text
    assert _totals(asked)["Total Entries"] == "0" and _rows(asked) == 0


async def test_vlcc_login_is_not_offered_other_shops(api, database, admin, token_for):
    vlcc = await create_vlcc(database, created_by=admin)
    (farmer, *_), = await _farmers(database, vlcc, 1, f"L{uuid4().hex[:5]}")
    await _farmer_entry(database, vlcc, farmer, datetime(2026, 4, 2, 7), quantity="7")

    page = (await api.get(VLCC_URL, headers=token_for(vlcc.user_id, Role.VLCC) | HTML)).text

    assert 'name="vlcc_id"' not in page and 'name="search"' in page
    assert _totals(page)["Total Qty (KG)"] == "7.00"


async def test_pager_keeps_filters_and_stays_short(api, database, admin, headers):
    vlcc = await create_vlcc(database, created_by=admin)
    (farmer, *_), = await _farmers(database, vlcc, 1, f"P{uuid4().hex[:5]}")
    for day in range(1, 26):
        await _farmer_entry(database, vlcc, farmer, datetime(2026, 5, day, 7))

    page = (await api.get(VLCC_URL, params={"vlcc_id": str(vlcc.id), "limit": 1, "page": 12, "milk_type": "0", "start_shift": "0"}, headers=headers)).text

    pager = page.split('aria-label="Pages"')[1].split("</nav>")[0]
    links = [link.replace("&amp;", "&") for link in re.findall(r'href="([^"]+)"', pager)]
    assert links and all(f"vlcc_id={vlcc.id}" in link and "milk_type=0" in link and "start_shift=0" in link and "limit=1" in link for link in links)
    numbers = re.findall(r'class="page-num[^"]*"[^>]*>(\d+)<', pager)
    assert numbers == ["10", "11", "12", "13", "14"]  # current page in the middle, two either side
    assert 'aria-current="page">12<' in pager


@pytest.mark.parametrize(
    "params",
    [
        {"limit": 0}, {"limit": -5}, {"limit": 100000}, {"page": 0}, {"vlcc_id": "not-a-uuid"}, {"milk_type": "9"},
        {"milk_type": "abc"}, {"start_shift": "5"}, {"date_from": "not-a-date"}, {"date_to": "2026-13-45"},
        {"search": "' OR 1=1 --"}, {"search": "<script>alert(1)</script>"},
    ],
)
@pytest.mark.parametrize("url", [VLCC_URL, MCC_URL])
async def test_hand_edited_links_never_break_the_page(api, headers, url, params):
    response = await api.get(url, params=params, headers=headers)
    assert response.status_code == 200
    assert "<script>alert(1)" not in response.text


async def test_filter_form_shows_what_was_chosen(api, database, admin, headers):
    vlcc = await create_vlcc(database, created_by=admin)
    await _offerable(database, vlcc)
    page = (await api.get(VLCC_URL, params={"vlcc_id": str(vlcc.id), "milk_type": "1", "date_from": "2026-06-01", "date_to": "2026-06-02", "start_shift": "1", "end_shift": "0"}, headers=headers)).text

    assert re.search(rf'value="{vlcc.id}" selected', page)
    assert 'value="1" selected>Buffalo' in page
    assert 'value="2026-06-01"' in page and 'value="2026-06-02"' in page
    assert 'value="1" selected>Evening' in page and 'value="0" selected>Morning' in page


# =========================================================
# MCC COLLECTIONS
# =========================================================


async def test_mcc_totals_and_filters(api, database, admin, headers):
    tag = uuid4().hex[:6]
    mcc_a = await _mcc(database, admin, f"MCC A {tag}")
    mcc_b = await _mcc(database, admin, f"MCC B {tag}")
    shop_a = await create_vlcc(database, created_by=admin)
    shop_b = await create_vlcc(database, created_by=admin)
    day = datetime(2026, 7, 1, 7)
    await _mcc_entry(database, mcc_a, shop_a, day, quantity="10", fat="4", snf="8", amount="100")
    await _mcc_entry(database, mcc_a, shop_b, day, shift=EVENING, milk=MilkType.BUFFALO, quantity="30", fat="6", snf="9", amount="300")
    await _mcc_entry(database, mcc_b, shop_a, day, quantity="60", fat="5", snf="8", amount="600")
    await _mcc_entry(database, mcc_a, shop_a, day, quantity="999", amount="999", deleted=True)

    async def totals(**params) -> dict[str, str]:
        page = (await api.get(MCC_URL, params={"date_from": "2026-07-01", "date_to": "2026-07-01", **params}, headers=headers)).text
        return _totals(page)

    assert await totals(mcc_id=str(mcc_a)) == {
        "Total Qty (KG)": "40.00", "Total Amount": "₹400", "Avg. FAT": "5.50%", "Avg. SNF": "8.75%", "Total Entries": "2",
    }
    assert (await totals(mcc_id=str(mcc_b)))["Total Qty (KG)"] == "60.00"
    assert (await totals(vlcc_id=str(shop_b.id)))["Total Qty (KG)"] == "30.00"
    assert (await totals(mcc_id=str(mcc_a), milk_type="1"))["Total Entries"] == "1"
    assert (await totals(mcc_id=str(mcc_a), start_shift="1", end_shift="1"))["Total Qty (KG)"] == "30.00"


async def test_mcc_search_finds_the_vlcc_by_name_or_code(api, database, admin, headers):
    tag = uuid4().hex[:8]
    mcc = await _mcc(database, admin, f"Hub {tag}")
    shop = await create_vlcc(database, created_by=admin)
    async with database.transaction() as session:
        await session.execute(update(VlccModel).where(VlccModel.id == shop.id).values(name=f"Amul {tag}", vlcc_code=f"C{tag}"))
    await _mcc_entry(database, mcc, shop, datetime(2026, 7, 2, 7), quantity="3")

    for term, found in ((f"Amul {tag}", "1"), (f"C{tag}", "1"), (f"Hub {tag}", "0")):
        page = (await api.get(MCC_URL, params={"search": term}, headers=headers)).text
        assert _totals(page)["Total Entries"] == found, term


async def test_unread_samples_do_not_drag_the_average_down(api, database, admin, headers):
    mcc = await _mcc(database, admin, f"Weight {uuid4().hex[:6]}")
    shop = await create_vlcc(database, created_by=admin)
    await _mcc_entry(database, mcc, shop, datetime(2026, 7, 3, 7), quantity="50", fat="4", snf="8", amount="500")
    await _mcc_entry(database, mcc, shop, datetime(2026, 7, 3, 8), quantity="50", fat="0", snf="0", amount="0")

    totals = _totals((await api.get(MCC_URL, params={"mcc_id": str(mcc)}, headers=headers)).text)

    assert totals["Total Qty (KG)"] == "100.00" and totals["Total Entries"] == "2"
    assert totals["Avg. FAT"] == "4.00%" and totals["Avg. SNF"] == "8.00%"


async def test_mcc_login_is_not_offered_other_centers(api, database, admin, token_for):
    user_id = await create_user(database, role=Role.MCC, created_by=admin)
    mcc_id = uuid4()
    async with database.transaction() as session:
        session.add(MccModel(id=mcc_id, user_id=user_id, code=f"M{mcc_id.hex[:6]}", name="Own", mcc_type=MccType.NORMAL, created_by=admin))
    shop = await create_vlcc(database, created_by=admin)
    await _mcc_entry(database, mcc_id, shop, datetime(2026, 7, 4, 7), quantity="9")

    page = (await api.get(MCC_URL, headers=token_for(user_id, Role.MCC) | HTML)).text

    assert 'name="mcc_id"' not in page and 'name="vlcc_id"' in page
    assert _totals(page)["Total Qty (KG)"] == "9.00"


async def test_vlcc_login_sees_only_its_own_supply_without_those_filters(api, database, admin, token_for):
    mcc = await _mcc(database, admin, f"Hub {uuid4().hex[:6]}")
    mine = await create_vlcc(database, created_by=admin)
    other = await create_vlcc(database, created_by=admin)
    await _mcc_entry(database, mcc, mine, datetime(2026, 7, 5, 7), quantity="11")
    await _mcc_entry(database, mcc, other, datetime(2026, 7, 5, 7), quantity="500")

    page = (await api.get(MCC_URL, headers=token_for(mine.user_id, Role.VLCC) | HTML)).text

    assert 'name="mcc_id"' not in page and 'name="vlcc_id"' not in page and 'name="search"' not in page
    assert _totals(page)["Total Qty (KG)"] == "11.00"


# =========================================================
# SMALL PIECES
# =========================================================


def test_a_true_average_is_not_truncated_below_itself():
    """Every entry at SNF 8.5: float addition must not turn the average into 8.49."""
    totals = totals_from_row(SimpleNamespace(
        quantity=11155.12, amount=475677.73, read_quantity=11155.12,
        fat_product=59511.5, snf_product=94818.5199999, entries=1068, all_entries=1080,
    ))
    assert fixed(totals.avg_snf) == "8.50"
    assert fixed(totals.avg_fat) == "5.33"  # 5.3349: a real value still truncates, as everywhere in the app
    assert (totals.entries, totals.deleted_entries) == (1068, 12)


async def test_many_entries_at_the_same_snf_average_to_exactly_that(api, database, admin, headers):
    vlcc = await create_vlcc(database, created_by=admin)
    (farmer, *_), = await _farmers(database, vlcc, 1, f"Q{uuid4().hex[:5]}")
    for number, quantity in enumerate(("3.6", "7.99", "17.35", "11.77", "5.24", "13.13", "9.07")):
        await _farmer_entry(database, vlcc, farmer, datetime(2026, 8, 1, 7 + number), quantity=quantity, snf="8.5", fat="4.1")

    totals = _totals((await api.get(VLCC_URL, params={"vlcc_id": str(vlcc.id)}, headers=headers)).text)

    assert (totals["Avg. SNF"], totals["Avg. FAT"]) == ("8.50%", "4.10%")


def test_period_puts_its_ends_in_order():
    period = CollectionPeriod(start_day=date(2026, 1, 5), end_day=date(2026, 1, 1), start_shift=EVENING, end_shift=MORNING).in_order()
    assert (period.start_day, period.start_shift, period.end_day, period.end_shift) == (date(2026, 1, 1), MORNING, date(2026, 1, 5), EVENING)


def test_period_with_one_end_is_left_alone():
    period = parse_period("2026-01-05", "", "1", "")
    assert (period.start_day, period.start_shift, period.end_day, period.end_shift) == (date(2026, 1, 5), EVENING, None, None)


