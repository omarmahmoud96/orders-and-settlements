"""Write side of the domain: every mutation is a transactional service function."""

from datetime import date
from decimal import Decimal

from django.db import transaction
from django.db.models import Q
from rest_framework.exceptions import NotFound

from .exceptions import (
    OrderHasSettlementsError,
    OrderLockedError,
    OverpaymentError,
    OverRefundError,
    ServiceError,
)
from .models import AuditEvent, AuditLog, LineItem, Order, Payment, Refund
from .money import ZERO, format_money, to_money
from .selectors import derive_status

EDITABLE_WHEN_LOCKED = ("customer", "due_date")


# --------------------------------------------------------------------- helpers


def _status(order: Order) -> str:
    return derive_status(order.total, order.amount_paid, order.due_date)


def _log(order, actor, event, *, status_from=None, status_to=None, **metadata):
    AuditLog.objects.create(
        order=order,
        actor=actor,
        event=event,
        status_from=status_from or "",
        status_to=status_to or "",
        metadata=metadata,
    )


def _log_status_change(order, actor, before: str, after: str, **metadata):
    if before != after:
        _log(
            order,
            actor,
            AuditEvent.STATUS_CHANGED,
            status_from=before,
            status_to=after,
            **metadata,
        )


def _write_line_items(order: Order, line_items: list[dict]) -> Decimal:
    """Replace the order's line items and recompute its total. Caller is in a transaction."""
    order.line_items.all().delete()
    LineItem.objects.bulk_create(
        [
            LineItem(
                order=order,
                description=item["description"],
                quantity=item["quantity"],
                unit_price=to_money(item["unit_price"]),
                position=index,
            )
            for index, item in enumerate(line_items)
        ]
    )
    total = to_money(
        sum(
            (to_money(item["unit_price"]) * item["quantity"] for item in line_items),
            Decimal("0.00"),
        )
    )
    order.total = total
    return total


def _locked_order(user, order_id: int) -> Order:
    """Fetch an order owned by ``user``, holding a row lock for the transaction."""
    try:
        return Order.objects.select_for_update().get(pk=order_id, owner=user)
    except Order.DoesNotExist as exc:
        raise NotFound("That order does not exist, or it belongs to another account.") from exc


# ---------------------------------------------------------------------- orders


@transaction.atomic
def create_order(*, user, customer: str, due_date: date, line_items: list[dict]) -> Order:
    if not line_items:
        raise ServiceError(
            "An order needs at least one line item.",
            details={"field": "line_items"},
        )

    order = Order(owner=user, customer=customer, due_date=due_date, amount_paid=ZERO)
    order.save()
    total = _write_line_items(order, line_items)

    if total <= ZERO:
        raise ServiceError(
            "An order total must be greater than zero. Check the quantities and unit prices.",
            details={"field": "line_items", "computed_total": str(total)},
        )

    order.save(update_fields=["total", "updated_at"])
    _log(
        order,
        user,
        AuditEvent.ORDER_CREATED,
        status_to=_status(order),
        total=str(total),
        line_item_count=len(line_items),
    )
    return order


@transaction.atomic
def update_order(
    *,
    user,
    order_id: int,
    customer: str | None = None,
    due_date: date | None = None,
    line_items: list[dict] | None = None,
) -> Order:
    order = _locked_order(user, order_id)
    order._has_settlements = (
        Payment.objects.filter(order=order).exists() or Refund.objects.filter(order=order).exists()
    )
    status_before = _status(order)

    if line_items is not None and order.is_locked:
        raise OrderLockedError(
            "This order has payments recorded against it, so its line items can no longer "
            f"be changed. You can still edit: {', '.join(EDITABLE_WHEN_LOCKED)}.",
            details={"editable_fields": list(EDITABLE_WHEN_LOCKED), "field": "line_items"},
        )

    changed = []
    if customer is not None and customer != order.customer:
        order.customer = customer
        changed.append("customer")
    if due_date is not None and due_date != order.due_date:
        order.due_date = due_date
        changed.append("due_date")

    if line_items is not None:
        if not line_items:
            raise ServiceError(
                "An order needs at least one line item.", details={"field": "line_items"}
            )
        total = _write_line_items(order, line_items)
        if total <= ZERO:
            raise ServiceError(
                "An order total must be greater than zero. Check the quantities and unit prices.",
                details={"field": "line_items", "computed_total": str(total)},
            )
        if total < order.amount_paid:
            raise ServiceError(
                f"The new total {format_money(total)} is less than the "
                f"{format_money(order.amount_paid)} already paid on this order.",
                details={"field": "line_items", "amount_paid": str(order.amount_paid)},
            )
        changed.append("line_items")

    if changed:
        order.save()
        _log(order, user, AuditEvent.ORDER_UPDATED, fields=changed)
        _log_status_change(order, user, status_before, _status(order))
    return order


@transaction.atomic
def delete_order(*, user, order_id: int) -> None:
    order = _locked_order(user, order_id)
    if Payment.objects.filter(order=order).exists() or Refund.objects.filter(order=order).exists():
        raise OrderHasSettlementsError(
            "This order has payments or refunds recorded against it and cannot be deleted. "
            "Refund the payments first if this order was raised in error.",
            details={"order_id": order.pk},
        )
    order.delete()


# ----------------------------------------------------------------- settlements


@transaction.atomic
def record_payment(
    *, user, order_id: int, amount, paid_on: date, note: str = ""
) -> tuple[Order, Payment]:
    amount = to_money(amount)
    if amount < Decimal("0.01"):
        raise ServiceError(
            "A payment must be at least $0.01.",
            details={"field": "amount", "minimum": "0.01"},
        )

    order = _locked_order(user, order_id)
    max_allowed = to_money(order.total - order.amount_paid)

    if amount > max_allowed:
        if max_allowed <= ZERO:
            message = (
                f"This order is already paid in full ({format_money(order.total)}), so a "
                f"payment of {format_money(amount)} cannot be recorded."
            )
        else:
            message = (
                f"A payment of {format_money(amount)} would exceed the amount due on this "
                f"order. The most you can record is {format_money(max_allowed)}."
            )
        raise OverpaymentError(
            message,
            details={
                "field": "amount",
                "order_total": str(order.total),
                "amount_paid": str(order.amount_paid),
                "max_allowed": str(max_allowed),
                "attempted": str(amount),
            },
        )

    status_before = _status(order)
    payment = Payment.objects.create(order=order, amount=amount, paid_on=paid_on, note=note or "")
    order.amount_paid = to_money(order.amount_paid + amount)
    order.save(update_fields=["amount_paid", "updated_at"])
    status_after = _status(order)

    _log(
        order,
        user,
        AuditEvent.PAYMENT_RECORDED,
        status_from=status_before,
        status_to=status_after,
        payment_id=payment.pk,
        amount=str(amount),
        amount_paid_after=str(order.amount_paid),
    )
    _log_status_change(order, user, status_before, status_after, payment_id=payment.pk)
    return order, payment


@transaction.atomic
def record_refund(
    *,
    user,
    order_id: int,
    amount,
    refunded_on: date,
    reason: str = "",
    refunded_payment_id: int | None = None,
) -> tuple[Order, Refund]:
    amount = to_money(amount)
    if amount < Decimal("0.01"):
        raise ServiceError(
            "A refund must be at least $0.01.",
            details={"field": "amount", "minimum": "0.01"},
        )

    order = _locked_order(user, order_id)
    max_allowed = to_money(order.amount_paid)

    if amount > max_allowed:
        raise OverRefundError(
            f"A refund of {format_money(amount)} is more than the "
            f"{format_money(max_allowed)} received on this order. "
            f"The most you can refund is {format_money(max_allowed)}.",
            details={
                "field": "amount",
                "amount_paid": str(order.amount_paid),
                "max_allowed": str(max_allowed),
                "attempted": str(amount),
            },
        )

    refunded_payment = None
    if refunded_payment_id is not None:
        refunded_payment = Payment.objects.filter(
            Q(pk=refunded_payment_id) & Q(order=order)
        ).first()
        if refunded_payment is None:
            raise ServiceError(
                "That payment does not belong to this order.",
                details={"field": "refunded_payment"},
            )

    status_before = _status(order)
    refund = Refund.objects.create(
        order=order,
        refunded_payment=refunded_payment,
        amount=amount,
        refunded_on=refunded_on,
        reason=reason or "",
    )
    order.amount_paid = to_money(order.amount_paid - amount)
    order.save(update_fields=["amount_paid", "updated_at"])
    status_after = _status(order)

    _log(
        order,
        user,
        AuditEvent.REFUND_ISSUED,
        status_from=status_before,
        status_to=status_after,
        refund_id=refund.pk,
        amount=str(amount),
        amount_paid_after=str(order.amount_paid),
    )
    _log_status_change(order, user, status_before, status_after, refund_id=refund.pk)
    return order, refund
