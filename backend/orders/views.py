from decimal import Decimal

from django.db.models import Case, Count, DecimalField, F, Prefetch, Sum, Value, When
from django.db.models.functions import Coalesce
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.generics import get_object_or_404
from rest_framework.response import Response
from rest_framework.views import APIView

from . import services
from .export import stream_orders_csv
from .filters import OrderFilter
from .models import AuditLog, OrderStatus, Payment, Refund
from .money import to_money
from .serializers import (
    AuditLogSerializer,
    OrderCreateSerializer,
    OrderDetailSerializer,
    OrderListSerializer,
    OrderUpdateSerializer,
    PaymentSerializer,
    PaymentWriteSerializer,
    RefundSerializer,
    RefundWriteSerializer,
)
from .selectors import AMOUNT_DUE_EXPR, order_queryset, status_filter_q

MONEY_FIELD = DecimalField(max_digits=12, decimal_places=2)
ZERO_MONEY = Value(Decimal("0.00"), output_field=MONEY_FIELD)


class OrderViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    """CRUD for orders plus the settlement sub-resources."""

    filterset_class = OrderFilter
    ordering_fields = ["created_at", "due_date", "total", "amount_paid", "amount_due", "customer"]
    ordering = ["-created_at"]

    def get_queryset(self):
        qs = order_queryset(self.request.user)
        if self.action in {"retrieve", "update", "partial_update"}:
            qs = qs.prefetch_related("line_items", "payments", "refunds")
        return qs

    def get_serializer_class(self):
        if self.action == "create":
            return OrderCreateSerializer
        if self.action in {"update", "partial_update"}:
            return OrderUpdateSerializer
        if self.action == "retrieve":
            return OrderDetailSerializer
        return OrderListSerializer

    def _detail_response(self, order, http_status=status.HTTP_200_OK):
        order = (
            self.get_queryset()
            .prefetch_related("line_items", "payments", "refunds")
            .get(pk=order.pk)
        )
        return Response(OrderDetailSerializer(order).data, status=http_status)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        order = services.create_order(user=request.user, **serializer.validated_data)
        return self._detail_response(order, status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        serializer = self.get_serializer(data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        order = services.update_order(
            user=request.user, order_id=self.kwargs["pk"], **serializer.validated_data
        )
        return self._detail_response(order)

    def partial_update(self, request, *args, **kwargs):
        return self.update(request, *args, partial=True, **kwargs)

    def destroy(self, request, *args, **kwargs):
        services.delete_order(user=request.user, order_id=self.kwargs["pk"])
        return Response(status=status.HTTP_204_NO_CONTENT)

    # ------------------------------------------------------------ settlements

    @action(detail=True, methods=["get", "post"], url_path="payments")
    def payments(self, request, pk=None):
        order = get_object_or_404(order_queryset(request.user), pk=pk)
        if request.method == "GET":
            queryset = Payment.objects.filter(order=order)
            page = self.paginate_queryset(queryset)
            serializer = PaymentSerializer(page if page is not None else queryset, many=True)
            if page is not None:
                return self.get_paginated_response(serializer.data)
            return Response(serializer.data)

        serializer = PaymentWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        order, payment = services.record_payment(
            user=request.user, order_id=order.pk, **serializer.validated_data
        )
        return Response(
            {
                "payment": PaymentSerializer(payment).data,
                "order": OrderDetailSerializer(
                    order_queryset(request.user)
                    .prefetch_related("line_items", "payments", "refunds")
                    .get(pk=order.pk)
                ).data,
            },
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=["get", "post"], url_path="refunds")
    def refunds(self, request, pk=None):
        order = get_object_or_404(order_queryset(request.user), pk=pk)
        if request.method == "GET":
            queryset = Refund.objects.filter(order=order)
            page = self.paginate_queryset(queryset)
            serializer = RefundSerializer(page if page is not None else queryset, many=True)
            if page is not None:
                return self.get_paginated_response(serializer.data)
            return Response(serializer.data)

        serializer = RefundWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        data["refunded_payment_id"] = data.pop("refunded_payment", None)
        order, refund = services.record_refund(user=request.user, order_id=order.pk, **data)
        return Response(
            {
                "refund": RefundSerializer(refund).data,
                "order": OrderDetailSerializer(
                    order_queryset(request.user)
                    .prefetch_related("line_items", "payments", "refunds")
                    .get(pk=order.pk)
                ).data,
            },
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=["get"], url_path="audit-log")
    def audit_log(self, request, pk=None):
        order = get_object_or_404(order_queryset(request.user), pk=pk)
        queryset = AuditLog.objects.filter(order=order).select_related("actor")
        page = self.paginate_queryset(queryset)
        serializer = AuditLogSerializer(page if page is not None else queryset, many=True)
        if page is not None:
            return self.get_paginated_response(serializer.data)
        return Response(serializer.data)

    # ---------------------------------------------------------------- export

    @action(detail=False, methods=["get"], url_path="export", pagination_class=None)
    def export(self, request):
        """CSV for a date range over ``created_at`` (``?from=``/``?to=``, inclusive)."""
        queryset = self.filter_queryset(self.get_queryset())
        date_from = request.query_params.get("from")
        date_to = request.query_params.get("to")
        if date_from:
            queryset = queryset.filter(created_at__date__gte=date_from)
        if date_to:
            queryset = queryset.filter(created_at__date__lte=date_to)
        queryset = queryset.prefetch_related(
            Prefetch("refunds", queryset=Refund.objects.only("amount", "order_id"))
        ).order_by("created_at")
        return stream_orders_csv(queryset, date_from=date_from, date_to=date_to)


class SummaryView(APIView):
    """Dashboard tiles: how many orders sit in each status and what they are worth."""

    def get(self, request):
        base = order_queryset(request.user)

        aggregates = {}
        for value in OrderStatus.values:
            condition = status_filter_q(value)
            aggregates[f"{value}__count"] = Count("pk", filter=condition)
            aggregates[f"{value}__total"] = Coalesce(
                Sum("total", filter=condition), ZERO_MONEY, output_field=MONEY_FIELD
            )
            aggregates[f"{value}__amount_due"] = Coalesce(
                Sum(AMOUNT_DUE_EXPR, filter=condition),
                ZERO_MONEY,
                output_field=MONEY_FIELD,
            )

        row = base.aggregate(
            **aggregates,
            order_count=Count("pk"),
            grand_total=Coalesce(Sum("total"), ZERO_MONEY, output_field=MONEY_FIELD),
            grand_paid=Coalesce(Sum("amount_paid"), ZERO_MONEY, output_field=MONEY_FIELD),
        )

        # Aggregates come back unquantised (Decimal("1000")); the API contract is
        # two decimal places for every amount.
        return Response(
            {
                "order_count": row["order_count"],
                "total": str(to_money(row["grand_total"])),
                "amount_paid": str(to_money(row["grand_paid"])),
                "amount_due": str(to_money(row["grand_total"] - row["grand_paid"])),
                "by_status": [
                    {
                        "status": value,
                        "count": row[f"{value}__count"],
                        "total": str(to_money(row[f"{value}__total"])),
                        "amount_due": str(to_money(row[f"{value}__amount_due"])),
                    }
                    for value in OrderStatus.values
                ],
            }
        )
