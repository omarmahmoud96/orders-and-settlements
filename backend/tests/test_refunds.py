"""Refunds (stretch goal)."""

from decimal import Decimal

import pytest

from orders import services
from orders.exceptions import OverRefundError, ServiceError
from orders.models import OrderStatus, Refund
from orders.selectors import derive_status


def test_refund_reduces_amount_paid(user, today, make_order):
    order = make_order()
    services.record_payment(user=user, order_id=order.pk, amount=Decimal("1000.00"), paid_on=today)

    order, refund = services.record_refund(
        user=user,
        order_id=order.pk,
        amount=Decimal("150.50"),
        refunded_on=today,
        reason="Damaged in transit",
    )
    assert order.amount_paid == Decimal("849.50")
    assert order.get_amount_due() == Decimal("150.50")
    assert refund.reason == "Damaged in transit"


def test_refund_cannot_exceed_what_was_received(user, today, make_order):
    order = make_order()
    services.record_payment(user=user, order_id=order.pk, amount=Decimal("400.00"), paid_on=today)

    with pytest.raises(OverRefundError) as exc:
        services.record_refund(
            user=user, order_id=order.pk, amount=Decimal("400.01"), refunded_on=today
        )

    assert exc.value.details["max_allowed"] == "400.00"
    order.refresh_from_db()
    assert order.amount_paid == Decimal("400.00")
    assert not Refund.objects.filter(order=order).exists()


def test_refund_on_an_unpaid_order_is_rejected(user, today, make_order):
    order = make_order()
    with pytest.raises(OverRefundError):
        services.record_refund(
            user=user, order_id=order.pk, amount=Decimal("1.00"), refunded_on=today
        )


@pytest.mark.parametrize("amount", ["0.00", "-1.00"])
def test_refund_below_a_cent_is_rejected(user, today, make_order, amount):
    order = make_order()
    services.record_payment(user=user, order_id=order.pk, amount=Decimal("500.00"), paid_on=today)
    with pytest.raises(ServiceError):
        services.record_refund(
            user=user, order_id=order.pk, amount=Decimal(amount), refunded_on=today
        )


def test_refunded_payment_must_belong_to_the_order(user, today, make_order):
    order_a = make_order(customer="A")
    order_b = make_order(customer="B")
    services.record_payment(user=user, order_id=order_a.pk, amount=Decimal("100.00"), paid_on=today)
    _, payment_b = services.record_payment(
        user=user, order_id=order_b.pk, amount=Decimal("100.00"), paid_on=today
    )

    with pytest.raises(ServiceError) as exc:
        services.record_refund(
            user=user,
            order_id=order_a.pk,
            amount=Decimal("50.00"),
            refunded_on=today,
            refunded_payment_id=payment_b.pk,
        )
    assert "does not belong" in exc.value.message


def test_refunding_everything_returns_the_order_to_pending(user, today, make_order):
    order = make_order()
    services.record_payment(user=user, order_id=order.pk, amount=Decimal("300.00"), paid_on=today)
    order, _ = services.record_refund(
        user=user, order_id=order.pk, amount=Decimal("300.00"), refunded_on=today
    )
    assert order.amount_paid == Decimal("0.00")
    assert (
        derive_status(order.total, order.amount_paid, order.due_date, today) == OrderStatus.PENDING
    )


def test_a_payment_can_be_recorded_again_after_a_refund_frees_headroom(user, today, make_order):
    order = make_order()
    services.record_payment(user=user, order_id=order.pk, amount=Decimal("1000.00"), paid_on=today)
    services.record_refund(user=user, order_id=order.pk, amount=Decimal("400.00"), refunded_on=today)

    order, _ = services.record_payment(
        user=user, order_id=order.pk, amount=Decimal("400.00"), paid_on=today
    )
    assert order.amount_paid == Decimal("1000.00")


@pytest.mark.django_db
def test_refund_endpoint(client, user, today, make_order):
    order = make_order()
    services.record_payment(user=user, order_id=order.pk, amount=Decimal("1000.00"), paid_on=today)

    response = client.post(
        f"/api/orders/{order.pk}/refunds/",
        {"amount": "250.00", "refunded_on": today.isoformat(), "reason": "Returned"},
        format="json",
    )
    assert response.status_code == 201
    assert response.data["order"]["amount_paid"] == "750.00"
    assert response.data["order"]["status"] == "partially_paid"
    assert response.data["refund"]["amount"] == "250.00"


@pytest.mark.django_db
def test_over_refund_endpoint_error_shape(client, user, today, make_order):
    order = make_order()
    services.record_payment(user=user, order_id=order.pk, amount=Decimal("100.00"), paid_on=today)

    response = client.post(
        f"/api/orders/{order.pk}/refunds/",
        {"amount": "500.00", "refunded_on": today.isoformat()},
        format="json",
    )
    assert response.status_code == 400
    assert response.data["error"]["code"] == "OVER_REFUND"
    assert response.data["error"]["details"]["max_allowed"] == "100.00"
