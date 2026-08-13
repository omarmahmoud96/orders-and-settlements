"""Status derivation: read side."""

from datetime import date
from decimal import Decimal

from django.db.models import Case, CharField, F, Q, QuerySet, Value, When
from django.utils import timezone

from .models import Order, OrderStatus


def today_or(today: date | None = None) -> date:
    return today if today is not None else timezone.localdate()


def derive_status(
    total: Decimal, amount_paid: Decimal, due_date: date, today: date | None = None
) -> str:
    """Python mirror of the SQL expression in :func:`orders_with_status`."""
    today = today_or(today)
    if amount_paid >= total:
        return OrderStatus.PAID
    if due_date < today:
        return OrderStatus.OVERDUE
    if amount_paid > Decimal("0.00"):
        return OrderStatus.PARTIALLY_PAID
    return OrderStatus.PENDING


def status_of(order: Order, today: date | None = None) -> str:
    """Status of an ``Order`` instance, preferring an annotation when present."""
    annotated = getattr(order, "status", None)
    if annotated is not None and today is None:
        return annotated
    return derive_status(order.total, order.amount_paid, order.due_date, today)


def amount_due_of(order: Order) -> Decimal:
    """Outstanding balance, preferring the annotation when present."""
    annotated = getattr(order, "amount_due", None)
    if annotated is not None:
        return annotated
    return order.get_amount_due()


#: Outstanding balance as a SQL expression.
AMOUNT_DUE_EXPR = F("total") - F("amount_paid")


def orders_with_status(qs: QuerySet, today: date | None = None) -> QuerySet:
    """Annotate a queryset with ``status`` and ``amount_due``."""
    today = today_or(today)
    return qs.annotate(
        amount_due=AMOUNT_DUE_EXPR,
        status=Case(
            When(amount_paid__gte=F("total"), then=Value(OrderStatus.PAID)),
            When(due_date__lt=today, then=Value(OrderStatus.OVERDUE)),
            When(amount_paid__gt=Decimal("0.00"), then=Value(OrderStatus.PARTIALLY_PAID)),
            default=Value(OrderStatus.PENDING),
            output_field=CharField(),
        ),
    )


def order_queryset(user, today: date | None = None) -> QuerySet:
    """The single entry point for reading orders."""
    return orders_with_status(Order.objects.filter(owner=user), today=today)


def status_filter_q(status: str, today: date | None = None) -> Q:
    """Equivalent of the CASE expression as a ``Q`` object, for aggregation queries."""
    today = today_or(today)
    paid = Q(amount_paid__gte=F("total"))
    overdue = ~paid & Q(due_date__lt=today)
    if status == OrderStatus.PAID:
        return paid
    if status == OrderStatus.OVERDUE:
        return overdue
    if status == OrderStatus.PARTIALLY_PAID:
        return ~paid & ~overdue & Q(amount_paid__gt=Decimal("0.00"))
    if status == OrderStatus.PENDING:
        return ~paid & ~overdue & Q(amount_paid__lte=Decimal("0.00"))
    raise ValueError(f"Unknown status: {status!r}")
