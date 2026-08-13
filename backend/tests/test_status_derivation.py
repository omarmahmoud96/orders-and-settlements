"""Status derivation: the four states, their precedence, and the edge cases."""

from datetime import timedelta
from decimal import Decimal

import pytest

from orders import services
from orders.models import Order, OrderStatus
from orders.selectors import derive_status, orders_with_status


@pytest.mark.parametrize(
    "total,paid,due_offset,expected",
    [
        # nothing paid, not yet due
        ("1000.00", "0.00", 7, OrderStatus.PENDING),
        # part paid, not yet due
        ("1000.00", "400.00", 7, OrderStatus.PARTIALLY_PAID),
        # paid in full, not yet due
        ("1000.00", "1000.00", 7, OrderStatus.PAID),
        # nothing paid, past due -> overdue outranks pending
        ("1000.00", "0.00", -1, OrderStatus.OVERDUE),
        # part paid, past due -> overdue outranks partially_paid
        ("1000.00", "400.00", -1, OrderStatus.OVERDUE),
        # EDGE CASE from the brief: was overdue, now settled in full -> paid
        ("1000.00", "1000.00", -30, OrderStatus.PAID),
        # due today is NOT overdue: only due_date < today counts
        ("1000.00", "0.00", 0, OrderStatus.PENDING),
        ("1000.00", "400.00", 0, OrderStatus.PARTIALLY_PAID),
        # a cent outstanding is still not paid
        ("1000.00", "999.99", 7, OrderStatus.PARTIALLY_PAID),
        ("1000.00", "999.99", -1, OrderStatus.OVERDUE),
    ],
)
def test_derive_status(total, paid, due_offset, expected, today):
    due_date = today + timedelta(days=due_offset)
    assert derive_status(Decimal(total), Decimal(paid), due_date, today) == expected


def test_overdue_order_paid_in_full_reports_paid(user, today):
    """The edge case the brief asks about, exercised end to end through the services."""
    order = services.create_order(
        user=user,
        customer="Umbrella Health",
        due_date=today - timedelta(days=30),
        line_items=[{"description": "Audit", "quantity": 1, "unit_price": Decimal("3200.00")}],
    )
    assert derive_status(order.total, order.amount_paid, order.due_date, today) == OrderStatus.OVERDUE

    order, _ = services.record_payment(
        user=user, order_id=order.pk, amount=Decimal("3200.00"), paid_on=today
    )
    assert derive_status(order.total, order.amount_paid, order.due_date, today) == OrderStatus.PAID

    annotated = orders_with_status(Order.objects.filter(pk=order.pk), today=today).get()
    assert annotated.status == OrderStatus.PAID


def test_refund_reopens_a_paid_order(user, today, make_order):
    order = make_order()
    services.record_payment(user=user, order_id=order.pk, amount=Decimal("1000.00"), paid_on=today)
    order.refresh_from_db()
    assert derive_status(order.total, order.amount_paid, order.due_date, today) == OrderStatus.PAID

    order, _ = services.record_refund(
        user=user, order_id=order.pk, amount=Decimal("250.00"), refunded_on=today
    )
    assert order.amount_paid == Decimal("750.00")
    assert (
        derive_status(order.total, order.amount_paid, order.due_date, today)
        == OrderStatus.PARTIALLY_PAID
    )


def test_refund_on_a_past_due_order_reopens_to_overdue(user, today):
    order = services.create_order(
        user=user,
        customer="Late Payer",
        due_date=today - timedelta(days=5),
        line_items=[{"description": "Work", "quantity": 1, "unit_price": Decimal("100.00")}],
    )
    services.record_payment(user=user, order_id=order.pk, amount=Decimal("100.00"), paid_on=today)
    order, _ = services.record_refund(
        user=user, order_id=order.pk, amount=Decimal("40.00"), refunded_on=today
    )
    assert (
        derive_status(order.total, order.amount_paid, order.due_date, today) == OrderStatus.OVERDUE
    )


def test_python_and_sql_status_agree_for_every_combination(user, today):
    """
    Build one order for each interesting (paid, due_date) combination and assert
    the annotation matches the Python function for all of them in a single query.
    """
    cases = []
    for due_offset in (-30, -1, 0, 1, 30):
        for paid in ("0.00", "0.01", "499.99", "999.99", "1000.00"):
            order = services.create_order(
                user=user,
                customer=f"case-{due_offset}-{paid}",
                due_date=today + timedelta(days=due_offset),
                line_items=[
                    {"description": "Item", "quantity": 2, "unit_price": Decimal("500.00")}
                ],
            )
            if Decimal(paid) > 0:
                services.record_payment(
                    user=user, order_id=order.pk, amount=Decimal(paid), paid_on=today
                )
            cases.append(order.pk)

    annotated = orders_with_status(Order.objects.filter(pk__in=cases), today=today)
    assert annotated.count() == len(cases)

    for order in annotated:
        expected = derive_status(order.total, order.amount_paid, order.due_date, today)
        assert order.status == expected, (
            f"SQL said {order.status!r} but Python said {expected!r} for "
            f"total={order.total} paid={order.amount_paid} due={order.due_date}"
        )
        assert order.amount_due == order.total - order.amount_paid


def test_amount_due_annotation_is_exact_to_the_cent(user, today, make_order):
    """Regression guard for decimal arithmetic done in SQL."""
    order = make_order()
    services.record_payment(user=user, order_id=order.pk, amount=Decimal("999.99"), paid_on=today)

    annotated = orders_with_status(Order.objects.filter(pk=order.pk), today=today).get()
    assert annotated.amount_due == Decimal("0.01")


@pytest.mark.django_db
def test_amount_due_is_serialised_to_two_places(client, user, today, make_order):
    order = make_order()
    services.record_payment(user=user, order_id=order.pk, amount=Decimal("999.99"), paid_on=today)

    listed = client.get("/api/orders/").data["results"][0]
    detail = client.get(f"/api/orders/{order.pk}/").data
    assert listed["amount_due"] == "0.01"
    assert detail["amount_due"] == "0.01"
    assert client.get("/api/summary/").data["amount_due"] == "0.01"


@pytest.mark.django_db
def test_status_filter_is_applied_in_sql(client, user, today, make_order):
    make_order(customer="Pending Co", due_in_days=7)

    partly = make_order(customer="Partial Co", due_in_days=7)
    services.record_payment(user=user, order_id=partly.pk, amount=Decimal("400.00"), paid_on=today)

    settled = make_order(customer="Paid Co", due_in_days=7)
    services.record_payment(user=user, order_id=settled.pk, amount=Decimal("1000.00"), paid_on=today)

    make_order(customer="Overdue Co", due_date=today - timedelta(days=3))

    for status_value, customer in [
        (OrderStatus.PENDING, "Pending Co"),
        (OrderStatus.PARTIALLY_PAID, "Partial Co"),
        (OrderStatus.PAID, "Paid Co"),
        (OrderStatus.OVERDUE, "Overdue Co"),
    ]:
        response = client.get("/api/orders/", {"status": status_value})
        assert response.status_code == 200
        results = response.data["results"]
        assert [row["customer"] for row in results] == [customer], status_value
        assert results[0]["status"] == status_value


@pytest.mark.django_db
def test_status_filter_accepts_multiple_values(client, user, today, make_order):
    make_order(customer="Pending Co", due_in_days=7)
    make_order(customer="Overdue Co", due_date=today - timedelta(days=3))
    settled = make_order(customer="Paid Co", due_in_days=7)
    services.record_payment(user=user, order_id=settled.pk, amount=Decimal("1000.00"), paid_on=today)

    response = client.get("/api/orders/?status=pending&status=overdue")
    assert response.status_code == 200
    assert {row["customer"] for row in response.data["results"]} == {"Pending Co", "Overdue Co"}
