"""Marketplace domain rules: who may sell, order status flow and slugs."""

import pytest

from app.modules.administration.domain.enums import Role
from app.modules.marketplace.domain.enums import OrderStatus
from app.modules.marketplace.domain.exceptions import SellingNotAllowedException
from app.modules.marketplace.domain.policy import SellerPolicy
from app.modules.marketplace.domain.slug import slugify


def test_super_admin_can_sell():
    assert SellerPolicy.can_sell(Role.SUPER_ADMIN)
    SellerPolicy.ensure_can_sell(Role.SUPER_ADMIN)


@pytest.mark.parametrize("role", [role for role in Role if role is not Role.SUPER_ADMIN])
def test_other_roles_cannot_sell_yet(role):
    assert not SellerPolicy.can_sell(role)
    with pytest.raises(SellingNotAllowedException):
        SellerPolicy.ensure_can_sell(role)


@pytest.mark.parametrize(
    ("current", "target"),
    [
        (OrderStatus.PLACED, OrderStatus.CONFIRMED),
        (OrderStatus.CONFIRMED, OrderStatus.PACKED),
        (OrderStatus.PACKED, OrderStatus.OUT_FOR_DELIVERY),
        (OrderStatus.OUT_FOR_DELIVERY, OrderStatus.DELIVERED),
        (OrderStatus.OUT_FOR_DELIVERY, OrderStatus.CANCELLED),
    ],
)
def test_allowed_order_moves(current, target):
    assert current.can_move_to(target)


@pytest.mark.parametrize(
    ("current", "target"),
    [
        (OrderStatus.PLACED, OrderStatus.DELIVERED),  # cannot skip steps
        (OrderStatus.PACKED, OrderStatus.CONFIRMED),  # cannot go back
        (OrderStatus.PLACED, OrderStatus.PLACED),
    ],
)
def test_refused_order_moves(current, target):
    assert not current.can_move_to(target)


@pytest.mark.parametrize("final", [OrderStatus.DELIVERED, OrderStatus.CANCELLED])
def test_finished_orders_cannot_move(final):
    assert [status for status in OrderStatus if final.can_move_to(status)] == []


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Desi Ghee 1 L!", "desi-ghee-1-l"),
        ("  Murrah   Buffalo  ", "murrah-buffalo"),
        ("Café Crème", "cafe-creme"),
        ("Ghee देसी", "ghee"),
    ],
)
def test_slugify(text, expected):
    assert slugify(text) == expected


def test_slug_without_latin_letters_is_still_usable():
    first, second = slugify("देसी घी"), slugify("देसी घी")
    assert first.startswith("item-") and len(first) > len("item-")
    assert first != second  # never collapses different listings into one URL


def test_slug_respects_max_length_without_trailing_hyphen():
    slug = slugify("word " * 100, max_length=22)
    assert len(slug) <= 22
    assert not slug.endswith("-")
