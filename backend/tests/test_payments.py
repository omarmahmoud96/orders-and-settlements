"""Payment allocation and the over-payment rule."""

from datetime import timedelta
from decimal import Decimal

import pytest
from django.db import IntegrityError, transaction

from orders import services
from orders.exceptions import OverpaymentError, ServiceError
from orders.models import Order, OrderStatus, Payment
from orders.selectors import derive_status


def test_multiple_partial_payments_sum_to_the_total(user, today, make_order):
    order = make_order()
    for amount in ("250.00", "250.00", "300.00", "200.00"):
        services.record_payment(
            user=user, order_id=order.pk, amount=Decimal(amount), paid_on=today
        )
    order.refresh_from_db()
    assert order.amount_paid == Decimal("1000.00")
    assert order.get_amount_due() == Decimal("0.00")
    assert derive_status(order.total, order.amount_paid, order.due_date, today) == OrderStatus.PAID
    assert order.payments.count() == 4


def test_payment_of_the_exact_remainder_is_allowed(user, today, make_order):
    order = make_order()
    services.record_payment(user=user, order_id=order.pk, amount=Decimal("999.99"), paid_on=today)
    order, _ = services.record_payment(
        user=user, order_id=order.pk, amount=Decimal("0.01"), paid_on=today
    )
    assert order.amount_paid == order.total


def test_overpayment_is_rejected_with_the_maximum_allowed(user, today, make_order):
    order = make_order()
    services.record_payment(user=user, order_id=order.pk, amount=Decimal("400.00"), paid_on=today)

    with pytest.raises(OverpaymentError) as exc:
        services.record_payment(
            user=user, order_id=order.pk, amount=Decimal("600.01"), paid_on=today
        )

    assert exc.value.details["max_allowed"] == "600.00"
    assert "600.00" in exc.value.message
    order.refresh_from_db()
    assert order.amount_paid == Decimal("400.00"), "rejected payment must not be recorded"
    assert order.payments.count() == 1


def test_payment_against_a_fully_paid_order_is_rejected(user, today, make_order):
    order = make_order()
    services.record_payment(user=user, order_id=order.pk, amount=Decimal("1000.00"), paid_on=today)

    with pytest.raises(OverpaymentError) as exc:
        services.record_payment(user=user, order_id=order.pk, amount=Decimal("1.00"), paid_on=today)

    assert exc.value.details["max_allowed"] == "0.00"
    assert "already paid in full" in exc.value.message


@pytest.mark.parametrize("amount", ["0.00", "0.001", "-5.00"])
def test_payments_below_a_cent_are_rejected(user, today, make_order, amount):
    order = make_order()
    with pytest.raises(ServiceError):
        services.record_payment(
            user=user, order_id=order.pk, amount=Decimal(amount), paid_on=today
        )
    assert not Payment.objects.filter(order=order).exists()


def test_database_constraint_backstops_the_service_check(user, make_order):
    """
    Even a write that bypasses the services layer cannot break the invariant.
    """
    order = make_order()
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            Order.objects.filter(pk=order.pk).update(amount_paid=Decimal("1000.01"))


# --------------------------------------------------------------------- the API


@pytest.mark.django_db
def test_the_assignment_sample_scenario(client, today):
    """
    The exact flow from the brief:
      2 x $500 = $1,000 due in 7 days
      -> pay 400  => partially_paid, 600 due
      -> pay 600  => paid, 0 due
      -> pay 1    => rejected with a clear error
    """
    create = client.post(
        "/api/orders/",
        {
            "customer": "Acme Corporation",
            "due_date": (today + timedelta(days=7)).isoformat(),
            "line_items": [
                {"description": "Consulting day", "quantity": 2, "unit_price": "500.00"}
            ],
        },
        format="json",
    )
    assert create.status_code == 201
    order_id = create.data["id"]
    assert create.data["total"] == "1000.00"
    assert create.data["status"] == "pending"
    assert create.data["amount_due"] == "1000.00"

    first = client.post(
        f"/api/orders/{order_id}/payments/",
        {"amount": "400.00", "paid_on": today.isoformat(), "note": "Deposit"},
        format="json",
    )
    assert first.status_code == 201
    assert first.data["order"]["status"] == "partially_paid"
    assert first.data["order"]["amount_paid"] == "400.00"
    assert first.data["order"]["amount_due"] == "600.00"

    second = client.post(
        f"/api/orders/{order_id}/payments/",
        {"amount": "600.00", "paid_on": today.isoformat()},
        format="json",
    )
    assert second.status_code == 201
    assert second.data["order"]["status"] == "paid"
    assert second.data["order"]["amount_due"] == "0.00"

    third = client.post(
        f"/api/orders/{order_id}/payments/",
        {"amount": "1.00", "paid_on": today.isoformat()},
        format="json",
    )
    assert third.status_code == 400
    error = third.data["error"]
    assert error["code"] == "OVERPAYMENT"
    assert error["details"]["max_allowed"] == "0.00"
    assert "$1.00" in error["message"]

    detail = client.get(f"/api/orders/{order_id}/")
    assert detail.data["amount_paid"] == "1000.00"
    assert len(detail.data["payments"]) == 2


@pytest.mark.django_db
def test_overpayment_error_shape_is_actionable(client, user, today, make_order):
    order = make_order()
    services.record_payment(user=user, order_id=order.pk, amount=Decimal("400.00"), paid_on=today)

    response = client.post(
        f"/api/orders/{order.pk}/payments/",
        {"amount": "700.00", "paid_on": today.isoformat()},
        format="json",
    )
    assert response.status_code == 400
    error = response.data["error"]
    assert error["code"] == "OVERPAYMENT"
    assert error["details"] == {
        "field": "amount",
        "order_total": "1000.00",
        "amount_paid": "400.00",
        "max_allowed": "600.00",
        "attempted": "700.00",
    }


@pytest.mark.django_db
def test_payment_history_is_returned_on_the_detail_page(client, user, today, make_order):
    order = make_order()
    services.record_payment(
        user=user, order_id=order.pk, amount=Decimal("100.00"), paid_on=today, note="First"
    )
    services.record_payment(
        user=user,
        order_id=order.pk,
        amount=Decimal("200.00"),
        paid_on=today - timedelta(days=1),
        note="Earlier",
    )
    response = client.get(f"/api/orders/{order.pk}/")
    payments = response.data["payments"]
    assert len(payments) == 2
    # newest payment date first
    assert payments[0]["note"] == "First"
    assert payments[1]["note"] == "Earlier"
