from datetime import date, timedelta
import pytest
from django.contrib.auth.models import Permission
from django.test import override_settings
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIClient
from apps.accounts.models import User
from apps.registry.models import (
    Department,
    DepartmentAccess,
    Supplier,
    Contract,
    Project,
)
from apps.evaluations.models import Criterion, Cycle, Invitation, Answer

pytestmark = pytest.mark.django_db


def invited():
    actor = User.objects.create_user(username="collaborator")
    other = User.objects.create_user(username="other")
    dept = Department.objects.create(code="D", name="D")
    for user in (actor, other):
        DepartmentAccess.objects.create(user=user, department=dept)
    supplier = Supplier.objects.create(code="S", name="S", tax_id="99000000000100")
    contract = Contract.objects.create(
        code="C", name="C", department=dept, supplier=supplier
    )
    cycle = Cycle.objects.create(
        year=date.today().year,
        quarter=1,
        opens=date.today() - timedelta(days=1),
        closes=date.today() + timedelta(days=1),
    )
    criterion = Criterion.objects.create(name="Qualidade")
    invitation = Invitation.objects.create(user=actor, contract=contract, cycle=cycle)
    invitation.criteria.add(criterion)
    return actor, other, invitation, criterion


def test_evaluation_privacy_na_and_duplicate_submission():
    actor, other, invitation, criterion = invited()
    client = APIClient()
    client.force_authenticate(other)
    payload = {
        "invitation": invitation.pk,
        "answers": [{"criterion": criterion.pk, "score": None}],
        "positives": "Comentário restrito",
    }
    assert (
        client.post("/api/v1/evaluations/", payload, format="json").status_code == 403
    )
    client.force_authenticate(actor)
    response = client.post("/api/v1/evaluations/", payload, format="json")
    assert response.status_code == 201, response.data
    assert Answer.objects.get().score is None
    assert (
        client.post("/api/v1/evaluations/", payload, format="json").status_code == 400
    )
    client.force_authenticate(other)
    assert client.get("/api/v1/evaluations/").data["count"] == 0


def test_closed_cycle_rejects_feedback():
    actor, _, invitation, criterion = invited()
    invitation.cycle.closes = date.today() - timedelta(days=1)
    invitation.cycle.save()
    client = APIClient()
    client.force_authenticate(actor)
    assert (
        client.post(
            "/api/v1/evaluations/",
            {
                "invitation": invitation.pk,
                "answers": [{"criterion": criterion.pk, "score": 5}],
            },
            format="json",
        ).status_code
        == 400
    )


def test_import_preview_and_unauthorized_department_are_safe():
    user = User.objects.create_user(username="importer")
    user.user_permissions.add(Permission.objects.get(codename="add_project"))
    dept = Department.objects.create(code="D", name="D")
    client = APIClient()
    client.force_authenticate(user)
    content = f"code;name;department\nIMPORT-1;Projeto importado;{dept.pk}\n".encode()

    def upload(commit="false"):
        return client.post(
            "/api/import/",
            {
                "resource": "projects",
                "commit": commit,
                "file": SimpleUploadedFile("projects.csv", content, "text/csv"),
            },
            format="multipart",
        )

    assert upload().status_code == 400
    DepartmentAccess.objects.create(user=user, department=dept)
    assert upload().data["committed"] is False
    assert not Project.objects.exists()
    assert upload("true").status_code == 200
    assert Project.objects.count() == 1


@override_settings(DEBUG=True)
def test_local_login_rate_limit():
    client = APIClient()
    for _ in range(5):
        assert (
            client.post(
                "/api/login/", {"username": "missing", "password": "wrong"}
            ).status_code
            == 400
        )
    response = client.post("/api/login/", {"username": "missing", "password": "wrong"})
    assert response.status_code == 429
    assert response["Retry-After"] == "900"
