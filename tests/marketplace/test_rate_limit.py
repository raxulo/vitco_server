"""Rate limits: the limiter itself and the store forms using it."""

from decimal import Decimal
from uuid import uuid4

import pytest

from app.core.rate_limit import SlidingWindowLimiter
from app.modules.administration.domain.enums import Role
from app.modules.marketplace.application.rate_limits import ACTION_LIMITS, StoreRateLimiter
from app.modules.marketplace.domain.enums import AnimalStatus
from app.modules.marketplace.domain.exceptions import TooManyRequestsException
from app.modules.marketplace.infrastructure.models import MarketplaceAnimalModel, MarketplaceAnimalTypeModel
from tests.dataexchange.factories import create_user

HTML = {"accept": "text/html"}


class _Clock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


def test_limit_then_retry_after_then_reset():
    clock = _Clock()
    limiter = SlidingWindowLimiter(clock=clock)

    assert [limiter.hit("a", 2, 60) for _ in range(2)] == [0, 0]
    assert limiter.hit("a", 2, 60) == 61  # the oldest hit leaves the window in a minute

    clock.now += 30
    assert 0 < limiter.hit("a", 2, 60) <= 31

    clock.now += 31
    assert limiter.hit("a", 2, 60) == 0


def test_window_slides_rather_than_resetting_all_at_once():
    clock = _Clock()
    limiter = SlidingWindowLimiter(clock=clock)
    limiter.hit("a", 2, 60)
    clock.now += 50
    limiter.hit("a", 2, 60)

    clock.now += 11  # only the first hit has left
    assert limiter.hit("a", 2, 60) == 0
    assert limiter.hit("a", 2, 60) > 0


def test_refused_attempts_do_not_extend_the_wait():
    clock = _Clock()
    limiter = SlidingWindowLimiter(clock=clock)
    limiter.hit("a", 1, 60)
    for _ in range(50):
        clock.now += 1
        limiter.hit("a", 1, 60)
    clock.now += 11
    assert limiter.hit("a", 1, 60) == 0


def test_keys_are_separate():
    limiter = SlidingWindowLimiter(clock=_Clock())
    limiter.hit("a", 1, 60)
    assert limiter.hit("a", 1, 60) > 0
    assert limiter.hit("b", 1, 60) == 0


def test_memory_is_bounded_and_the_oldest_key_goes_first():
    limiter = SlidingWindowLimiter(max_keys=100, clock=_Clock())
    limiter.hit("first", 1, 60)
    for number in range(1000):
        limiter.hit(f"key-{number}", 1, 60)

    assert len(limiter) == 100
    assert limiter.hit("first", 1, 60) == 0  # it was forgotten
    assert limiter.hit("key-999", 1, 60) > 0  # a recent one was not


def test_store_limits_by_action_and_client():
    store = StoreRateLimiter(SlidingWindowLimiter(clock=_Clock()))
    for _ in range(ACTION_LIMITS["enquiry"]):
        store.ensure_allowed("enquiry", "1.1.1.1")
    with pytest.raises(TooManyRequestsException) as error:
        store.ensure_allowed("enquiry", "1.1.1.1")
    assert error.value.retry_after > 0

    store.ensure_allowed("track", "1.1.1.1")  # another action
    store.ensure_allowed("enquiry", "2.2.2.2")  # another client


def test_switched_off_never_refuses():
    store = StoreRateLimiter(SlidingWindowLimiter(clock=_Clock()), enabled=False)
    for _ in range(1000):
        store.ensure_allowed("enquiry", "1.1.1.1")


# =========================================================
# THROUGH THE REAL APP
# =========================================================


@pytest.fixture
async def strict_limits(api):
    """Turns limits on for this test only, with a fresh count."""
    from app.main import app

    store = app.state.application.container.resolve(StoreRateLimiter)  # the container is frozen, so change it in place
    original = (store._limiter, store._enabled)
    store._limiter, store._enabled = SlidingWindowLimiter(), True
    yield
    store._limiter, store._enabled = original


@pytest.fixture
async def animal_slug(database) -> str:
    seller = await create_user(database, role=Role.SUPER_ADMIN)
    type_id, slug = uuid4(), f"a-{uuid4().hex}"
    async with database.transaction() as session:
        session.add(MarketplaceAnimalTypeModel(id=type_id, name=f"Cow {type_id.hex}", slug=f"t-{type_id.hex}"))
        await session.flush()
        session.add(MarketplaceAnimalModel(seller_user_id=seller, animal_type_id=type_id, title="Gir", slug=slug, price=Decimal("1"), status=AnimalStatus.PUBLISHED))
    return slug


@pytest.mark.parametrize(
    ("action", "url", "data"),
    [("track", "/marketplace/track", {"order_ref": "X", "phone": "1"}), ("checkout", "/marketplace/checkout", {})],
)
async def test_web_forms_answer_429_with_a_friendly_page(api, strict_limits, action, url, data):
    for _ in range(ACTION_LIMITS[action]):
        assert (await api.post(url, data=data, headers=HTML)).status_code != 429

    response = await api.post(url, data=data, headers=HTML)

    assert response.status_code == 429
    assert int(response.headers["retry-after"]) > 0
    assert "Please wait a few minutes" in response.text and "css/store.css" in response.text


async def test_enquiry_is_limited_before_anything_is_saved(api, strict_limits, animal_slug):
    url = f"/marketplace/animals/{animal_slug}/enquiry"
    for number in range(ACTION_LIMITS["enquiry"]):
        form = {"buyer_name": "Asha", "buyer_phone": f"98765{number:05d}"}
        assert (await api.post(url, data=form, headers=HTML, follow_redirects=False)).status_code == 303

    blocked = await api.post(url, data={"buyer_name": "Asha", "buyer_phone": "9000000000"}, headers=HTML)
    assert blocked.status_code == 429


async def test_api_answers_429_as_json(api, strict_limits):
    body = {"order_ref": "X", "phone": "1"}
    for _ in range(ACTION_LIMITS["track"]):
        assert (await api.post("/api/v1/marketplace/orders/track", json=body)).status_code == 404

    response = await api.post("/api/v1/marketplace/orders/track", json=body)

    assert response.status_code == 429
    assert int(response.headers["retry-after"]) > 0
    assert response.json()["error"]["code"] == "MARKETPLACE_TOO_MANY_REQUESTS"


async def test_web_and_api_share_one_limit(api, strict_limits):
    """Otherwise someone guessing could simply switch to the other door."""
    for _ in range(ACTION_LIMITS["track"]):
        await api.post("/marketplace/track", data={"order_ref": "X", "phone": "1"}, headers=HTML)
    response = await api.post("/api/v1/marketplace/orders/track", json={"order_ref": "X", "phone": "1"})
    assert response.status_code == 429
