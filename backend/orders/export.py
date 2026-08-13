"""CSV export of orders for a date range (stretch goal)."""

import csv
from datetime import date

from django.http import StreamingHttpResponse

from .selectors import status_of

COLUMNS = [
    "order_id",
    "customer",
    "status",
    "due_date",
    "order_total",
    "amount_paid",
    "amount_due",
    "payment_count",
    "refund_total",
    "created_at",
]


class _Echo:
    """A file-like object whose ``write`` returns the value, for csv streaming."""

    def write(self, value):
        return value


def stream_orders_csv(queryset, *, date_from: date | None, date_to: date | None):
    """Stream the queryset as CSV."""
    writer = csv.writer(_Echo())

    def rows():
        yield writer.writerow(COLUMNS)
        for order in queryset.iterator(chunk_size=200):
            refund_total = sum((refund.amount for refund in order.refunds.all()), start=0)
            yield writer.writerow(
                [
                    order.pk,
                    order.customer,
                    status_of(order),
                    order.due_date.isoformat(),
                    f"{order.total:.2f}",
                    f"{order.amount_paid:.2f}",
                    f"{order.get_amount_due():.2f}",
                    order.payments.count(),
                    f"{refund_total:.2f}",
                    order.created_at.isoformat(),
                ]
            )

    suffix = ""
    if date_from or date_to:
        suffix = f"_{date_from or 'start'}_to_{date_to or 'today'}"
    filename = f"orders{suffix}.csv"

    response = StreamingHttpResponse(rows(), content_type="text/csv")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response
