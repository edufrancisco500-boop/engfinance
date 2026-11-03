import pytest
from django.test import override_settings
from django.contrib.auth.models import Permission
from rest_framework.test import APIClient
from apps.accounts.models import User
from apps.registry.models import AuditEvent, Department, DepartmentAccess, Portfolio

pytestmark = pytest.mark.django_db


def test_anonymous_cannot_read():
    assert APIClient().get("/api/v1/portfolios/").status_code == 403


def test_scope_blocks_read_and_write():
    user = User.objects.create_user(username="analyst")
    user.user_permissions.set(
        Permission.objects.filter(codename__in=["view_portfolio", "add_portfolio"])
    )
    own = Department.objects.create(code="A", name="A")
    other = Department.objects.create(code="B", name="B")
    DepartmentAccess.objects.create(user=user, department=own)
    Portfolio.objects.create(code="SECRET", name="Restrita", department=other)
    client = APIClient()
    client.force_authenticate(user)
    assert client.get("/api/v1/portfolios/").json()["count"] == 0
    response = client.post(
        "/api/v1/portfolios/", {"code": "X", "name": "X", "department": other.pk}
    )
    assert response.status_code == 400
    assert not Portfolio.objects.filter(code="X").exists()
    response = client.post(
        "/api/v1/portfolios/", {"code": "Y", "name": "Y", "department": own.pk}
    )
    assert response.status_code == 201
    assert AuditEvent.objects.filter(actor=user, action="create").count() == 1


def test_login_requires_csrf():
    client = APIClient(enforce_csrf_checks=True)
    assert (
        client.post("/api/login/", {"username": "x", "password": "x"}).status_code
        == 403
    )


def test_detail_and_update_cannot_escape_scope():
    user = User.objects.create_user(username="reader")
    user.user_permissions.set(
        Permission.objects.filter(codename__in=["view_portfolio", "change_portfolio"])
    )
    department = Department.objects.create(code="D", name="D")
    hidden = Portfolio.objects.create(code="P", name="Privada", department=department)
    client = APIClient()
    client.force_authenticate(user)
    url = f"/api/v1/portfolios/{hidden.pk}/"
    assert client.get(url).status_code == 404
    assert client.patch(url, {"name": "Alterada"}).status_code == 404
    hidden.refresh_from_db()
    assert hidden.name == "Privada"


def test_update_preserves_before_and_after_and_disallows_delete():
    user = User.objects.create_superuser(username="admin", password="test")
    department = Department.objects.create(code="D", name="D")
    portfolio = Portfolio.objects.create(code="P", name="Antes", department=department)
    client = APIClient()
    client.force_authenticate(user)
    url = f"/api/v1/portfolios/{portfolio.pk}/"
    assert client.patch(url, {"name": "Depois"}).status_code == 200
    event = AuditEvent.objects.get(action="update")
    assert event.before["name"] == "Antes"
    assert event.after["name"] == "Depois"
    assert client.delete(url).status_code == 405


@override_settings(DEBUG=True, CSRF_TRUSTED_ORIGINS=["http://127.0.0.1:5173"])
def test_development_proxy_login_requires_token_and_trusted_origin():
    User.objects.create_user(username="developer", password="local-test-password")
    client = APIClient(enforce_csrf_checks=True)
    client.get("/api/session/")
    token = client.cookies["csrftoken"].value
    data = {"username": "developer", "password": "local-test-password"}
    assert (
        client.post(
            "/api/login/", data, HTTP_ORIGIN="http://127.0.0.1:5173"
        ).status_code
        == 403
    )
    assert (
        client.post(
            "/api/login/",
            data,
            HTTP_X_CSRFTOKEN=token,
            HTTP_ORIGIN="https://untrusted.example",
        ).status_code
        == 403
    )
    assert (
        client.post(
            "/api/login/",
            data,
            HTTP_X_CSRFTOKEN=token,
            HTTP_ORIGIN="http://127.0.0.1:5173",
        ).status_code
        == 200
    )
