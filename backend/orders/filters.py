import django_filters

from .models import Order, OrderStatus


class OrderFilter(django_filters.FilterSet):
    """Dashboard filters."""

    status = django_filters.MultipleChoiceFilter(
        field_name="status", choices=OrderStatus.choices
    )
    customer = django_filters.CharFilter(field_name="customer", lookup_expr="icontains")
    due_after = django_filters.DateFilter(field_name="due_date", lookup_expr="gte")
    due_before = django_filters.DateFilter(field_name="due_date", lookup_expr="lte")
    created_after = django_filters.DateFilter(field_name="created_at", lookup_expr="date__gte")
    created_before = django_filters.DateFilter(field_name="created_at", lookup_expr="date__lte")

    class Meta:
        model = Order
        fields = ["status", "customer", "due_after", "due_before", "created_after", "created_before"]
