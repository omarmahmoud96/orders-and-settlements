"""Authentication, and the rule that a user only ever sees their own data."""

from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model

from orders import services

User = get_user_model()

pytestmark = pytest.mark.django_db


def test_register_returns_a_usable_token_pair(anon_client):
    response = anon_client.post(
        "/api/auth/register/",
        {"email": "New.User@Example.com", "password": "a-strong-password-42", "name": "New User"},
        format="json",
    )
    assert response.status_code == 201
    assert response.data["user"]["email"] == "new.user@example.com", "email is normalised"
    assert response.data["access"] and response.data["refresh"]

    anon_client.credentials(HTTP_AUTHORIZATION=f"Bearer {response.data['access']}")
    me = anon_client.get("/api/auth/me/")
    assert me.status_code == 200
    assert me.data["email"] == "new.user@example.com"


def test_register_rejects_a_duplicate_email(anon_client, user):
    response = anon_client.post(
        "/api/auth/register/",
        {"email": user.email.upper(), "password": "another-strong-password"},
        format="json",
    )
    assert response.status_code == 400
    assert response.data["error"]["code"] == "VALIDATION_ERROR"
    assert "already exists" in response.data["error"]["message"]


def test_register_rejects_a_weak_password(anon_client):
    response = anon_client.post(
        "/api/auth/register/", {"email": "weak@example.com", "password": "1234"}, format="json"
    )
    assert response.status_code == 400
    assert response.data["error"]["code"] == "VALIDATION_ERROR"


def test_login_then_call_an_endpoint(anon_client, user):
    response = anon_client.post(
        "/api/auth/login/",
        {"email": "OWNER@example.com", "password": "s3cret-password"},
        format="json",
    )
    assert response.status_code == 200
    anon_client.credentials(HTTP_AUTHORIZATION=f"Bearer {response.data['access']}")
    assert anon_client.get("/api/orders/").status_code == 200


def test_login_with_a_bad_password_fails(anon_client, user):
    response = anon_client.post(
        "/api/auth/login/", {"email": user.email, "password": "wrong"}, format="json"
    )
    assert response.status_code == 401
    assert response.data["error"]["code"] == "AUTH_REQUIRED"


def test_anonymous_requests_are_rejected(anon_client, make_order):
    order = make_order()
    for url in ["/api/orders/", f"/api/orders/{order.pk}/", "/api/summary/"]:
        response = anon_client.get(url)
        assert response.status_code == 401
        assert response.data["error"]["code"] == "AUTH_REQUIRED"


# --------------------------------------------------------------------- tenancy


def test_orders_list_only_shows_your_own(client, other_client, make_order, other_user):
    make_order(customer="Mine")
    make_order(owner=other_user, customer="Theirs")

    mine = client.get("/api/orders/")
    assert [row["customer"] for row in mine.data["results"]] == ["Mine"]

    theirs = other_client.get("/api/orders/")
    assert [row["customer"] for row in theirs.data["results"]] == ["Theirs"]


@pytest.mark.parametrize(
    "path_suffix", ["", "payments/", "refunds/", "audit-log/"]
)
def test_another_users_order_is_a_404_not_a_403(other_client, make_order, path_suffix):
    """404 rather than 403: a 403 would confirm the id exists."""
    order = make_order()
    response = other_client.get(f"/api/orders/{order.pk}/{path_suffix}")
    assert response.status_code == 404
    assert response.data["error"]["code"] == "NOT_FOUND"


def test_cannot_record_a_payment_on_another_users_order(other_client, make_order, today):
    order = make_order()
    response = other_client.post(
        f"/api/orders/{order.pk}/payments/",
        {"amount": "10.00", "paid_on": today.isoformat()},
        format="json",
    )
    assert response.status_code == 404
    order.refresh_from_db()
    assert order.amount_paid == Decimal("0.00")


def test_cannot_edit_or_delete_another_users_order(other_client, make_order):
    order = make_order()
    assert other_client.patch(f"/api/orders/{order.pk}/", {"customer": "Hijacked"}, format="json").status_code == 404
    assert other_client.delete(f"/api/orders/{order.pk}/").status_code == 404
    order.refresh_from_db()
    assert order.customer == "Acme Corporation"


def test_summary_only_counts_your_own_orders(client, user, other_user, make_order, today):
    make_order(customer="Mine")
    other = make_order(owner=other_user, customer="Theirs")
    services.record_payment(
        user=other_user, order_id=other.pk, amount=Decimal("500.00"), paid_on=today
    )

    response = client.get("/api/summary/")
    assert response.data["order_count"] == 1
    assert response.data["total"] == "1000.00"
    assert response.data["amount_paid"] == "0.00"


def test_export_only_includes_your_own_orders(client, other_user, make_order):
    make_order(customer="Mine")
    make_order(owner=other_user, customer="Theirs")

    response = client.get("/api/orders/export/")
    assert response.status_code == 200
    body = b"".join(response.streaming_content).decode()
    assert "Mine" in body
    assert "Theirs" not in body
