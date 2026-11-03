from io import StringIO

import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import override_settings

from apps.registry.models import (
    AuditEvent,
    Contract,
    Department,
    DepartmentAccess,
    Portfolio,
    Project,
    Supplier,
)


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_demo_can_run_twice_without_duplicates_and_grants_scope():
    user = get_user_model().objects.create_user(username="demo-owner")
    for _ in range(2):
        call_command("seed_demo", user=user.username, stdout=StringIO())
    for model in (Department, Portfolio, Project, Supplier, Contract):
        assert model.objects.count() == 10
    assert DepartmentAccess.objects.filter(user=user).count() == 10
    assert AuditEvent.objects.count() == 60
    assert all(
        contract.department_id
        == Portfolio.objects.get(code=contract.code.replace("CTR", "CAR")).department_id
        for contract in Contract.objects.all()
    )
