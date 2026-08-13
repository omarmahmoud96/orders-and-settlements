"""Two payments submitted at the same instant must not overpay an order."""

import threading
from decimal import Decimal

import pytest
from django.db import connections, transaction

from orders import services
from orders.exceptions import OverpaymentError
from orders.models import Order


@pytest.mark.django_db(transaction=True)
def test_simultaneous_payments_cannot_overpay(django_db_setup, django_db_blocker, user, today):
    order = services.create_order(
        user=user,
        customer="Race Condition Ltd",
        due_date=today,
        line_items=[{"description": "Item", "quantity": 2, "unit_price": Decimal("500.00")}],
    )

    # Each payment fits on its own (600 <= 1000) but together they overshoot.
    results: list[object] = []
    barrier = threading.Barrier(2, timeout=10)

    def attempt(amount):
        try:
            barrier.wait()
            services.record_payment(
                user=user, order_id=order.pk, amount=Decimal(amount), paid_on=today
            )
            results.append("ok")
        except OverpaymentError:
            results.append("rejected")
        except Exception as exc:  # surfaced in the assertion below
            results.append(exc)
        finally:
            connections.close_all()

    threads = [threading.Thread(target=attempt, args=(amount,)) for amount in ("600.00", "600.00")]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=30)

    assert sorted(str(result) for result in results) == ["ok", "rejected"], results

    order.refresh_from_db()
    assert order.amount_paid == Decimal("600.00")
    assert order.amount_paid <= order.total
    assert order.payments.count() == 1


@pytest.mark.django_db
def test_payment_is_rolled_back_entirely_when_rejected(user, today, make_order):
    """
    A rejected payment must leave nothing behind: no Payment row, no change to
    amount_paid, no audit entry. The whole service call is one transaction.
    """
    order = make_order()
    services.record_payment(user=user, order_id=order.pk, amount=Decimal("999.00"), paid_on=today)
    audit_before = order.audit_entries.count()

    with pytest.raises(OverpaymentError):
        services.record_payment(user=user, order_id=order.pk, amount=Decimal("2.00"), paid_on=today)

    order.refresh_from_db()
    assert order.amount_paid == Decimal("999.00")
    assert order.payments.count() == 1
    assert order.audit_entries.count() == audit_before


@pytest.mark.django_db
def test_the_invariant_holds_after_a_long_sequence_of_writes(user, today, make_order):
    """Fuzz-ish sanity check: many interleaved payments and refunds, invariant intact."""
    order = make_order(
        line_items=[{"description": "Item", "quantity": 1, "unit_price": Decimal("100.00")}]
    )
    for _ in range(10):
        services.record_payment(user=user, order_id=order.pk, amount=Decimal("10.00"), paid_on=today)
        order.refresh_from_db()
        assert order.amount_paid <= order.total

    for _ in range(5):
        services.record_refund(
            user=user, order_id=order.pk, amount=Decimal("10.00"), refunded_on=today
        )
        order.refresh_from_db()
        assert order.amount_paid >= Decimal("0.00")

    assert order.amount_paid == Decimal("50.00")
    assert Order.objects.get(pk=order.pk).get_amount_due() == Decimal("50.00")
