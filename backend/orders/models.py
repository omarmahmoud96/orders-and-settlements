from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import F, Q

from .money import to_money

MONEY = {"max_digits": 12, "decimal_places": 2}


class OrderStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    PARTIALLY_PAID = "partially_paid", "Partially paid"
    PAID = "paid", "Paid"
    OVERDUE = "overdue", "Overdue"


class AuditEvent(models.TextChoices):
    ORDER_CREATED = "order_created", "Order created"
    ORDER_UPDATED = "order_updated", "Order updated"
    PAYMENT_RECORDED = "payment_recorded", "Payment recorded"
    REFUND_ISSUED = "refund_issued", "Refund issued"
    STATUS_CHANGED = "status_changed", "Status changed"


class Order(models.Model):
    """A customer order with line items and a payment history."""

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="orders"
    )
    customer = models.CharField(max_length=255)
    due_date = models.DateField()
    total = models.DecimalField(**MONEY, default=Decimal("0.00"))
    amount_paid = models.DecimalField(**MONEY, default=Decimal("0.00"))
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(fields=["owner", "due_date"]),
            models.Index(fields=["owner", "-created_at"]),
        ]
        constraints = [
            models.CheckConstraint(
                condition=Q(total__gte=Decimal("0.00")), name="order_total_non_negative"
            ),
            models.CheckConstraint(
                condition=Q(amount_paid__gte=Decimal("0.00")),
                name="order_amount_paid_non_negative",
            ),
            models.CheckConstraint(
                condition=Q(amount_paid__lte=F("total")),
                name="order_amount_paid_not_over_total",
            ),
        ]

    def __str__(self):
        return f"Order #{self.pk} - {self.customer}"

    def get_amount_due(self) -> Decimal:
        """
        Outstanding balance.

        Deliberately a method and not a property: ``orders_with_status``
        annotates an ``amount_due`` attribute onto instances, and Django applies
        annotations with ``setattr`` -- which raises against a read-only
        property. Keeping the names disjoint avoids that whole class of bug.
        """
        return to_money(self.total - self.amount_paid)

    @property
    def is_locked(self) -> bool:
        """True once money has moved against this order."""
        if hasattr(self, "_has_settlements"):
            return bool(self._has_settlements)
        return self.payments.exists() or self.refunds.exists()

    def recalculate_total(self) -> Decimal:
        """Recompute ``total`` from the current line items. Does not save."""
        self.total = to_money(
            sum((item.line_total for item in self.line_items.all()), Decimal("0.00"))
        )
        return self.total


class LineItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="line_items")
    description = models.CharField(max_length=255)
    quantity = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    unit_price = models.DecimalField(**MONEY, validators=[MinValueValidator(Decimal("0.00"))])
    position = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["position", "id"]
        constraints = [
            models.CheckConstraint(condition=Q(quantity__gte=1), name="lineitem_quantity_min_1"),
            models.CheckConstraint(
                condition=Q(unit_price__gte=Decimal("0.00")),
                name="lineitem_unit_price_non_negative",
            ),
        ]

    def __str__(self):
        return f"{self.quantity} x {self.description}"

    @property
    def line_total(self) -> Decimal:
        return to_money(self.unit_price * self.quantity)


class Payment(models.Model):
    """A settlement recorded against an order. Always a positive amount."""

    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="payments")
    amount = models.DecimalField(**MONEY, validators=[MinValueValidator(Decimal("0.01"))])
    paid_on = models.DateField()
    note = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-paid_on", "-created_at", "-id"]
        indexes = [models.Index(fields=["order", "-paid_on"])]
        constraints = [
            models.CheckConstraint(
                condition=Q(amount__gte=Decimal("0.01")), name="payment_amount_min"
            )
        ]

    def __str__(self):
        return f"Payment {self.amount} on order #{self.order_id}"


class Refund(models.Model):
    """Money returned to the customer."""

    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="refunds")
    refunded_payment = models.ForeignKey(
        Payment,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="refunds",
        help_text="Optional: the payment this refund reverses.",
    )
    amount = models.DecimalField(**MONEY, validators=[MinValueValidator(Decimal("0.01"))])
    refunded_on = models.DateField()
    reason = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-refunded_on", "-created_at", "-id"]
        indexes = [models.Index(fields=["order", "-refunded_on"])]
        constraints = [
            models.CheckConstraint(
                condition=Q(amount__gte=Decimal("0.01")), name="refund_amount_min"
            )
        ]

    def __str__(self):
        return f"Refund {self.amount} on order #{self.order_id}"


class AuditLog(models.Model):
    """Append-only history of everything that happened to an order."""

    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="audit_entries")
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_entries",
    )
    event = models.CharField(max_length=32, choices=AuditEvent.choices)
    status_from = models.CharField(max_length=16, blank=True, default="")
    status_to = models.CharField(max_length=16, blank=True, default="")
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [models.Index(fields=["order", "-created_at"])]

    def __str__(self):
        return f"{self.event} on order #{self.order_id}"
