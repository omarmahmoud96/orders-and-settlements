from decimal import Decimal

from rest_framework import serializers

from .models import AuditLog, LineItem, Order, OrderStatus, Payment, Refund
from .money import to_money
from .selectors import amount_due_of, status_of


class LineItemSerializer(serializers.ModelSerializer):
    line_total = serializers.SerializerMethodField()

    class Meta:
        model = LineItem
        fields = ["id", "description", "quantity", "unit_price", "line_total"]
        read_only_fields = ["id", "line_total"]

    def get_line_total(self, obj) -> str:
        return str(obj.line_total)


class LineItemWriteSerializer(serializers.Serializer):
    description = serializers.CharField(max_length=255, allow_blank=False)
    quantity = serializers.IntegerField(min_value=1)
    unit_price = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal("0.00"))

    def validate_unit_price(self, value):
        return to_money(value)


class PaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payment
        fields = ["id", "amount", "paid_on", "note", "created_at"]
        read_only_fields = ["id", "created_at"]


class PaymentWriteSerializer(serializers.Serializer):
    amount = serializers.DecimalField(
        max_digits=12, decimal_places=2, min_value=Decimal("0.01")
    )
    paid_on = serializers.DateField()
    note = serializers.CharField(required=False, allow_blank=True, default="")


class RefundSerializer(serializers.ModelSerializer):
    class Meta:
        model = Refund
        fields = ["id", "amount", "refunded_on", "reason", "refunded_payment", "created_at"]
        read_only_fields = ["id", "created_at"]


class RefundWriteSerializer(serializers.Serializer):
    amount = serializers.DecimalField(
        max_digits=12, decimal_places=2, min_value=Decimal("0.01")
    )
    refunded_on = serializers.DateField()
    reason = serializers.CharField(required=False, allow_blank=True, default="")
    refunded_payment = serializers.IntegerField(required=False, allow_null=True)


class AuditLogSerializer(serializers.ModelSerializer):
    actor_email = serializers.CharField(source="actor.email", default=None, read_only=True)

    class Meta:
        model = AuditLog
        fields = [
            "id",
            "event",
            "status_from",
            "status_to",
            "metadata",
            "actor_email",
            "created_at",
        ]
        read_only_fields = fields


class OrderSummaryMixin(serializers.Serializer):
    status = serializers.SerializerMethodField()
    amount_due = serializers.SerializerMethodField()

    def get_status(self, obj) -> str:
        return str(status_of(obj))

    def get_amount_due(self, obj) -> str:
        return str(to_money(amount_due_of(obj)))


class OrderListSerializer(OrderSummaryMixin, serializers.ModelSerializer):
    class Meta:
        model = Order
        fields = [
            "id",
            "customer",
            "due_date",
            "total",
            "amount_paid",
            "amount_due",
            "status",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class OrderDetailSerializer(OrderSummaryMixin, serializers.ModelSerializer):
    line_items = LineItemSerializer(many=True, read_only=True)
    payments = PaymentSerializer(many=True, read_only=True)
    refunds = RefundSerializer(many=True, read_only=True)
    is_locked = serializers.BooleanField(read_only=True)
    editable_fields = serializers.SerializerMethodField()

    class Meta:
        model = Order
        fields = [
            "id",
            "customer",
            "due_date",
            "total",
            "amount_paid",
            "amount_due",
            "status",
            "is_locked",
            "editable_fields",
            "line_items",
            "payments",
            "refunds",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields

    def get_editable_fields(self, obj) -> list[str]:
        from .services import EDITABLE_WHEN_LOCKED

        if obj.is_locked:
            return list(EDITABLE_WHEN_LOCKED)
        return [*EDITABLE_WHEN_LOCKED, "line_items"]


class OrderCreateSerializer(serializers.Serializer):
    customer = serializers.CharField(max_length=255, allow_blank=False)
    due_date = serializers.DateField()
    line_items = LineItemWriteSerializer(many=True, allow_empty=False)


class OrderUpdateSerializer(serializers.Serializer):
    customer = serializers.CharField(max_length=255, allow_blank=False, required=False)
    due_date = serializers.DateField(required=False)
    line_items = LineItemWriteSerializer(many=True, allow_empty=False, required=False)

    def validate(self, attrs):
        if not attrs:
            raise serializers.ValidationError(
                "Provide at least one of: customer, due_date, line_items."
            )
        return attrs


class StatusBucketSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=OrderStatus.choices)
    count = serializers.IntegerField()
    total = serializers.CharField()
    amount_due = serializers.CharField()
