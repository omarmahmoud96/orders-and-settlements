from datetime import timedelta
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APIClient

from orders import services

User = get_user_model()


@pytest.fixture
def today():
    return timezone.localdate()


@pytest.fixture
def user(db):
    return User.objects.create_user(email="owner@example.com", password="s3cret-password")


@pytest.fixture
def other_user(db):
    return User.objects.create_user(email="stranger@example.com", password="s3cret-password")


@pytest.fixture
def client(user):
    api = APIClient()
    api.force_authenticate(user=user)
    return api


@pytest.fixture
def other_client(other_user):
    api = APIClient()
    api.force_authenticate(user=other_user)
    return api


@pytest.fixture
def anon_client():
    return APIClient()


@pytest.fixture
def make_order(user, today):
    """Create an order for the default user; defaults to the assignment's sample."""

    def _make(
        *,
        owner=None,
        customer="Acme Corporation",
        due_in_days=7,
        line_items=None,
        due_date=None,
    ):
        return services.create_order(
            user=owner or user,
            customer=customer,
            due_date=due_date or (today + timedelta(days=due_in_days)),
            line_items=line_items
            or [{"description": "Consulting day", "quantity": 2, "unit_price": Decimal("500.00")}],
        )

    return _make
