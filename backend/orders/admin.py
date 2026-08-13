from django.contrib import admin

from .models import AuditLog, LineItem, Order, Payment, Refund


class LineItemInline(admin.TabularInline):
    model = LineItem
    extra = 0


class PaymentInline(admin.TabularInline):
    model = Payment
    extra = 0


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ["id", "customer", "owner", "due_date", "total", "amount_paid"]
    list_filter = ["due_date"]
    search_fields = ["customer", "owner__email"]
    inlines = [LineItemInline, PaymentInline]


@admin.register(Refund)
class RefundAdmin(admin.ModelAdmin):
    list_display = ["id", "order", "amount", "refunded_on"]


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ["id", "order", "event", "status_from", "status_to", "created_at"]
    list_filter = ["event"]
