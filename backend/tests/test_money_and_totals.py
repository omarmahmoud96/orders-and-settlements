"""Line item arithmetic and order totals."""

from decimal import Decimal

import pytest

from orders import services
from orders.exceptions import ServiceError
from orders.money import to_money


@pytest.mark.parametrize(
    "value,expected",
    [
        (Decimal("1000"), Decimal("1000.00")),
        (0.1, Decimal("0.10")),          # float goes via str, not binary approximation
        ("19.995", Decimal("20.00")),    # half rounds away from zero
        ("19.994", Decimal("19.99")),
        ("-2.005", Decimal("-2.01")),
        (7, Decimal("7.00")),
    ],
)
def test_to_money_quantises_to_cents(value, expected):
    assert to_money(value) == expected


@pytest.mark.parametrize("value", ["abc", None, float("nan"), float("inf")])
def test_to_money_rejects_nonsense(value):
    with pytest.raises(ValueError):
        to_money(value)


def test_subtotal_is_sum_of_line_totals(make_order):
    order = make_order(
        line_items=[
            {"description": "Consulting day", "quantity": 2, "unit_price": Decimal("500.00")},
            {"description": "Travel", "quantity": 3, "unit_price": Decimal("42.50")},
            {"description": "Licence", "quantity": 1, "unit_price": Decimal("99.99")},
        ]
    )
    # 1000.00 + 127.50 + 99.99
    assert order.total == Decimal("1227.49")
    assert [item.line_total for item in order.line_items.all()] == [
        Decimal("1000.00"),
        Decimal("127.50"),
        Decimal("99.99"),
    ]


def test_the_assignment_sample_order_totals_1000(make_order):
    order = make_order()
    assert order.total == Decimal("1000.00")
    assert order.amount_paid == Decimal("0.00")
    assert order.get_amount_due() == Decimal("1000.00")


def test_fractional_unit_prices_stay_exact(make_order):
    """A case that would drift if amounts were floats: 10 x 249.99."""
    order = make_order(
        line_items=[{"description": "Widget", "quantity": 10, "unit_price": Decimal("249.99")}]
    )
    assert order.total == Decimal("2499.90")


def test_line_items_preserve_input_order(make_order):
    order = make_order(
        line_items=[
            {"description": "Third", "quantity": 1, "unit_price": Decimal("3.00")},
            {"description": "First", "quantity": 1, "unit_price": Decimal("1.00")},
            {"description": "Second", "quantity": 1, "unit_price": Decimal("2.00")},
        ]
    )
    assert [item.description for item in order.line_items.all()] == ["Third", "First", "Second"]


def test_order_requires_at_least_one_line_item(user, today):
    with pytest.raises(ServiceError):
        services.create_order(user=user, customer="Nobody", due_date=today, line_items=[])


def test_zero_total_order_is_rejected(user, today):
    with pytest.raises(ServiceError) as exc:
        services.create_order(
            user=user,
            customer="Freebie Ltd",
            due_date=today,
            line_items=[{"description": "Gift", "quantity": 1, "unit_price": Decimal("0.00")}],
        )
    assert "greater than zero" in exc.value.message


@pytest.mark.django_db
def test_quantity_below_one_is_rejected_by_the_api(client, today):
    response = client.post(
        "/api/orders/",
        {
            "customer": "Acme",
            "due_date": today.isoformat(),
            "line_items": [{"description": "Nothing", "quantity": 0, "unit_price": "10.00"}],
        },
        format="json",
    )
    assert response.status_code == 400
    assert response.data["error"]["code"] == "VALIDATION_ERROR"


@pytest.mark.django_db
def test_totals_are_serialised_as_strings_not_floats(client, make_order):
    order = make_order()
    response = client.get(f"/api/orders/{order.pk}/")
    assert response.status_code == 200
    assert response.data["total"] == "1000.00"
    assert isinstance(response.data["total"], str)
    assert isinstance(response.data["amount_due"], str)
