"""Order CRUD, the editability rule, audit log and CSV export."""

import csv
import io
from datetime import timedelta
from decimal import Decimal

import pytest

from orders import services
from orders.exceptions import OrderHasSettlementsError, OrderLockedError
from orders.models import AuditEvent, Order, OrderStatus

pytestmark = pytest.mark.django_db


def test_create_order_via_the_api(client, today):
    response = client.post(
        "/api/orders/",
        {
            "customer": "Northwind Traders",
            "due_date": (today + timedelta(days=14)).isoformat(),
            "line_items": [
                {"description": "Workshop", "quantity": 1, "unit_price": "1200.00"},
                {"description": "Seats", "quantity": 8, "unit_price": "75.00"},
            ],
        },
        format="json",
    )
    assert response.status_code == 201
    assert response.data["total"] == "1800.00"
    assert response.data["status"] == "pending"
    assert len(response.data["line_items"]) == 2
    assert response.data["line_items"][0]["line_total"] == "1200.00"
    assert response.data["is_locked"] is False
    assert "line_items" in response.data["editable_fields"]


def test_update_an_unpaid_order(client, make_order, today):
    order = make_order()
    response = client.patch(
        f"/api/orders/{order.pk}/",
        {
            "customer": "Renamed Ltd",
            "line_items": [{"description": "Revised", "quantity": 3, "unit_price": "100.00"}],
        },
        format="json",
    )
    assert response.status_code == 200
    assert response.data["customer"] == "Renamed Ltd"
    assert response.data["total"] == "300.00"
    assert len(response.data["line_items"]) == 1


def test_line_items_are_frozen_once_a_payment_exists(client, user, make_order, today):
    """
    Documented decision: after the first settlement the line items (and so the
    total) are read-only; customer and due date stay editable.
    """
    order = make_order()
    services.record_payment(user=user, order_id=order.pk, amount=Decimal("400.00"), paid_on=today)

    blocked = client.patch(
        f"/api/orders/{order.pk}/",
        {"line_items": [{"description": "Cheaper", "quantity": 1, "unit_price": "10.00"}]},
        format="json",
    )
    assert blocked.status_code == 409
    assert blocked.data["error"]["code"] == "ORDER_LOCKED"
    assert blocked.data["error"]["details"]["editable_fields"] == ["customer", "due_date"]

    order.refresh_from_db()
    assert order.total == Decimal("1000.00")

    allowed = client.patch(
        f"/api/orders/{order.pk}/",
        {"customer": "Acme (renamed)", "due_date": (today + timedelta(days=30)).isoformat()},
        format="json",
    )
    assert allowed.status_code == 200
    assert allowed.data["customer"] == "Acme (renamed)"
    assert allowed.data["is_locked"] is True
    assert allowed.data["editable_fields"] == ["customer", "due_date"]


def test_reducing_the_total_below_amount_paid_is_impossible(user, make_order, today):
    """Belt and braces: even without the lock the arithmetic guard would refuse."""
    order = make_order()
    services.record_payment(user=user, order_id=order.pk, amount=Decimal("400.00"), paid_on=today)
    with pytest.raises(OrderLockedError):
        services.update_order(
            user=user,
            order_id=order.pk,
            line_items=[{"description": "Tiny", "quantity": 1, "unit_price": Decimal("1.00")}],
        )


def test_changing_the_due_date_can_change_the_status(client, make_order, today):
    order = make_order(due_in_days=7)
    response = client.patch(
        f"/api/orders/{order.pk}/",
        {"due_date": (today - timedelta(days=1)).isoformat()},
        format="json",
    )
    assert response.status_code == 200
    assert response.data["status"] == "overdue"


def test_delete_an_unpaid_order(client, make_order):
    order = make_order()
    assert client.delete(f"/api/orders/{order.pk}/").status_code == 204
    assert not Order.objects.filter(pk=order.pk).exists()


def test_delete_is_blocked_once_money_has_moved(client, user, make_order, today):
    order = make_order()
    services.record_payment(user=user, order_id=order.pk, amount=Decimal("400.00"), paid_on=today)

    response = client.delete(f"/api/orders/{order.pk}/")
    assert response.status_code == 409
    assert response.data["error"]["code"] == "CONFLICT"
    assert Order.objects.filter(pk=order.pk).exists()


def test_update_with_an_empty_body_is_rejected(client, make_order):
    response = client.patch(f"/api/orders/{make_order().pk}/", {}, format="json")
    assert response.status_code == 400
    assert response.data["error"]["code"] == "VALIDATION_ERROR"


# ------------------------------------------------------------------ audit log


def test_audit_log_records_creation_payment_and_status_change(client, user, make_order, today):
    order = make_order()
    services.record_payment(user=user, order_id=order.pk, amount=Decimal("400.00"), paid_on=today)
    services.record_payment(user=user, order_id=order.pk, amount=Decimal("600.00"), paid_on=today)

    response = client.get(f"/api/orders/{order.pk}/audit-log/")
    assert response.status_code == 200
    events = [row["event"] for row in response.data["results"]]

    assert events.count(AuditEvent.ORDER_CREATED) == 1
    assert events.count(AuditEvent.PAYMENT_RECORDED) == 2
    assert events.count(AuditEvent.STATUS_CHANGED) == 2

    transitions = [
        (row["status_from"], row["status_to"])
        for row in response.data["results"]
        if row["event"] == AuditEvent.STATUS_CHANGED
    ]
    assert (OrderStatus.PENDING, OrderStatus.PARTIALLY_PAID) in transitions
    assert (OrderStatus.PARTIALLY_PAID, OrderStatus.PAID) in transitions


def test_a_payment_that_does_not_change_status_logs_no_transition(client, user, make_order, today):
    order = make_order()
    services.record_payment(user=user, order_id=order.pk, amount=Decimal("100.00"), paid_on=today)
    services.record_payment(user=user, order_id=order.pk, amount=Decimal("100.00"), paid_on=today)

    response = client.get(f"/api/orders/{order.pk}/audit-log/")
    events = [row["event"] for row in response.data["results"]]
    # both payments stay inside partially_paid, so only the first transition is logged
    assert events.count(AuditEvent.STATUS_CHANGED) == 1


def test_audit_log_records_the_actor(client, user, make_order):
    make_order()
    order = Order.objects.get()
    response = client.get(f"/api/orders/{order.pk}/audit-log/")
    assert response.data["results"][0]["actor_email"] == user.email


# ---------------------------------------------------------------- csv export


def _read_csv(response):
    body = b"".join(response.streaming_content).decode()
    return list(csv.DictReader(io.StringIO(body)))


def test_csv_export_contains_the_derived_columns(client, user, make_order, today):
    order = make_order(customer="Acme Corporation")
    services.record_payment(user=user, order_id=order.pk, amount=Decimal("400.00"), paid_on=today)

    response = client.get("/api/orders/export/")
    assert response.status_code == 200
    assert response["Content-Disposition"].startswith("attachment; filename=")

    rows = _read_csv(response)
    assert len(rows) == 1
    row = rows[0]
    assert row["customer"] == "Acme Corporation"
    assert row["status"] == "partially_paid"
    assert row["order_total"] == "1000.00"
    assert row["amount_paid"] == "400.00"
    assert row["amount_due"] == "600.00"
    assert row["payment_count"] == "1"


def test_csv_export_honours_the_date_range(client, make_order, today):
    make_order(customer="In range")
    tomorrow = today + timedelta(days=1)

    included = _read_csv(client.get("/api/orders/export/", {"from": today.isoformat()}))
    assert len(included) == 1

    excluded = _read_csv(client.get("/api/orders/export/", {"from": tomorrow.isoformat()}))
    assert excluded == []


def test_csv_export_honours_the_status_filter(client, user, make_order, today):
    make_order(customer="Pending Co")
    paid = make_order(customer="Paid Co")
    services.record_payment(user=user, order_id=paid.pk, amount=Decimal("1000.00"), paid_on=today)

    rows = _read_csv(client.get("/api/orders/export/", {"status": "paid"}))
    assert [row["customer"] for row in rows] == ["Paid Co"]


# -------------------------------------------------------------------- summary


def test_summary_buckets_orders_by_status(client, user, make_order, today):
    make_order(customer="Pending Co", due_in_days=7)

    partial = make_order(customer="Partial Co", due_in_days=7)
    services.record_payment(user=user, order_id=partial.pk, amount=Decimal("400.00"), paid_on=today)

    paid = make_order(customer="Paid Co", due_in_days=7)
    services.record_payment(user=user, order_id=paid.pk, amount=Decimal("1000.00"), paid_on=today)

    make_order(customer="Overdue Co", due_date=today - timedelta(days=2))

    response = client.get("/api/summary/")
    assert response.status_code == 200
    buckets = {row["status"]: row for row in response.data["by_status"]}

    assert buckets["pending"]["count"] == 1
    assert buckets["partially_paid"]["count"] == 1
    assert buckets["paid"]["count"] == 1
    assert buckets["overdue"]["count"] == 1

    assert buckets["partially_paid"]["amount_due"] == "600.00"
    assert buckets["paid"]["amount_due"] == "0.00"

    assert response.data["order_count"] == 4
    assert response.data["total"] == "4000.00"
    assert response.data["amount_paid"] == "1400.00"
    assert response.data["amount_due"] == "2600.00"


def test_summary_buckets_match_the_list_filter(client, user, make_order, today):
    """The summary and the list must not disagree about what is in each bucket."""
    make_order(customer="Pending Co", due_in_days=7)
    make_order(customer="Overdue Co", due_date=today - timedelta(days=2))
    paid = make_order(customer="Paid Co")
    services.record_payment(user=user, order_id=paid.pk, amount=Decimal("1000.00"), paid_on=today)

    summary = {row["status"]: row["count"] for row in client.get("/api/summary/").data["by_status"]}
    for status_value, expected in summary.items():
        listed = client.get("/api/orders/", {"status": status_value}).data["count"]
        assert listed == expected, status_value
