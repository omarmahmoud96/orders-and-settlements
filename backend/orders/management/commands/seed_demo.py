"""
Seed a demo account with orders covering every status, including the edge cases.

    python manage.py seed_demo

Idempotent: re-running wipes the demo user's orders and rebuilds them.
"""

from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from orders import services
from orders.models import Order
from orders.selectors import status_of

User = get_user_model()

DEMO_EMAIL = "demo@example.com"
DEMO_PASSWORD = "demo-password-123"


class Command(BaseCommand):
    help = "Create a demo user with orders in every status."

    def add_arguments(self, parser):
        parser.add_argument("--email", default=DEMO_EMAIL)
        parser.add_argument("--password", default=DEMO_PASSWORD)

    @transaction.atomic
    def handle(self, *args, **options):
        email = options["email"].lower()
        today = timezone.localdate()

        user, created = User.objects.get_or_create(email=email, defaults={"name": "Demo User"})
        user.set_password(options["password"])
        user.save()

        removed, _ = Order.objects.filter(owner=user).delete()
        if removed:
            self.stdout.write(f"Cleared {removed} existing rows for {email}.")

        # 1. pending -- nothing paid, not yet due
        services.create_order(
            user=user,
            customer="Northwind Traders",
            due_date=today + timedelta(days=14),
            line_items=[
                {"description": "Onboarding workshop", "quantity": 1, "unit_price": Decimal("1200.00")},
                {"description": "Training seats", "quantity": 8, "unit_price": Decimal("75.00")},
            ],
        )

        # 2. partially_paid -- the assignment's sample scenario, mid-flow
        order = services.create_order(
            user=user,
            customer="Acme Corporation",
            due_date=today + timedelta(days=7),
            line_items=[
                {"description": "Consulting day", "quantity": 2, "unit_price": Decimal("500.00")},
            ],
        )
        services.record_payment(
            user=user, order_id=order.pk, amount=Decimal("400.00"), paid_on=today,
            note="Deposit received by bank transfer",
        )

        # 3. paid -- settled across two payments
        order = services.create_order(
            user=user,
            customer="Globex Industries",
            due_date=today + timedelta(days=3),
            line_items=[
                {"description": "Annual licence", "quantity": 1, "unit_price": Decimal("2400.00")},
                {"description": "Priority support", "quantity": 1, "unit_price": Decimal("600.00")},
            ],
        )
        services.record_payment(
            user=user, order_id=order.pk, amount=Decimal("1500.00"),
            paid_on=today - timedelta(days=5), note="First instalment",
        )
        services.record_payment(
            user=user, order_id=order.pk, amount=Decimal("1500.00"),
            paid_on=today - timedelta(days=1), note="Balance settled",
        )

        # 4. overdue -- past due, part paid
        order = services.create_order(
            user=user,
            customer="Initech LLC",
            due_date=today - timedelta(days=10),
            line_items=[
                {"description": "Migration project", "quantity": 1, "unit_price": Decimal("5000.00")},
            ],
        )
        services.record_payment(
            user=user, order_id=order.pk, amount=Decimal("1000.00"),
            paid_on=today - timedelta(days=20), note="Partial payment, balance chased",
        )

        # 5. edge case: was overdue, now settled in full -> reports `paid`, not `overdue`
        order = services.create_order(
            user=user,
            customer="Umbrella Health",
            due_date=today - timedelta(days=30),
            line_items=[
                {"description": "Compliance audit", "quantity": 1, "unit_price": Decimal("3200.00")},
            ],
        )
        services.record_payment(
            user=user, order_id=order.pk, amount=Decimal("3200.00"),
            paid_on=today - timedelta(days=2), note="Settled late, in full",
        )

        # 6. edge case: a refund reopens a fully paid order
        order = services.create_order(
            user=user,
            customer="Stark Manufacturing",
            due_date=today + timedelta(days=21),
            line_items=[
                {"description": "Hardware units", "quantity": 10, "unit_price": Decimal("249.99")},
            ],
        )
        services.record_payment(
            user=user, order_id=order.pk, amount=Decimal("2499.90"),
            paid_on=today - timedelta(days=3), note="Paid in full on receipt",
        )
        services.record_refund(
            user=user, order_id=order.pk, amount=Decimal("499.98"),
            refunded_on=today, reason="Two units returned damaged",
        )

        self.stdout.write(self.style.SUCCESS(f"\nSeeded {'new' if created else 'existing'} user {email}"))
        self.stdout.write(f"  password: {options['password']}\n")
        for order in Order.objects.filter(owner=user).order_by("id"):
            self.stdout.write(
                f"  #{order.pk} {order.customer:<24} {status_of(order):<15} "
                f"total {order.total:>9} paid {order.amount_paid:>9} due {order.get_amount_due():>9}"
            )
