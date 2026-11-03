from datetime import date
from decimal import Decimal

import pytest
from django.test import override_settings
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.finance.models import Allocation, Budget, Document, Parcel, Policy
from apps.finance.selectors import dashboard
from apps.registry.models import (
    Coordination,
    Contract,
    Department,
    Portfolio,
    Project,
    Supplier,
)

pytestmark = pytest.mark.django_db


@pytest.fixture
def filter_data():
    user = User.objects.create_superuser(username="filter-tester", password="test")
    Policy.objects.create(name="Política de teste", demo=True)
    year = date.today().year
    values = []
    for index in (1, 2):
        dept = Department.objects.create(code=f"D{index}", name=f"Gerência {index}")
        coordination = Coordination.objects.create(
            code=f"CO{index}", name=f"Coordenação {index}", department=dept
        )
        portfolio = Portfolio.objects.create(
            code=f"CA{index}", name=f"Carteira {index}", department=dept
        )
        project = Project.objects.create(
            code=f"P{index}",
            name=f"Projeto {index}",
            department=dept,
            coordination=coordination,
        )
        supplier = Supplier.objects.create(
            code=f"S{index}", name=f"Fornecedor {index}", tax_id=f"99000000000{index}00"
        )
        contract = Contract.objects.create(
            code=f"C{index}",
            name=f"Contrato {index}",
            department=dept,
            supplier=supplier,
            original_value=1000,
            status="ACTIVE" if index == 1 else "SUSPENDED",
        )
        budget = Budget.objects.create(
            portfolio=portfolio,
            year=year,
            category="CAPEX" if index == 1 else "OPEX",
            amount=1000,
            status="APPROVED",
            reason="Teste de filtro",
            created_by=user,
        )
        allocation = Allocation.objects.create(
            budget=budget,
            project=project,
            amount=800,
            status="APPROVED",
            reason="Teste de filtro",
            created_by=user,
        )
        for kind, amount in [
            ("COMMITMENT", 100 * index),
            ("MEASUREMENT", 50 * index),
            ("PAYMENT", 25 * index),
        ]:
            document = Document.objects.create(
                contract=contract,
                kind=kind,
                reference=f"TEST-{index}-{kind}",
                date=date(year, index, 10),
                amount=amount,
                status="APPROVED",
                reason="Teste de filtro",
                created_by=user,
            )
            Parcel.objects.create(
                document=document, allocation=allocation, amount=amount
            )
        values.append(
            {
                "department": dept.pk,
                "coordination": coordination.pk,
                "portfolio": portfolio.pk,
                "project": project.pk,
                "supplier": supplier.pk,
                "contract": contract.pk,
            }
        )
    return user, year, values


@pytest.mark.parametrize(
    "field,value,expected",
    [
        ("month", "1", "100.00"),
        ("month", "2", "200.00"),
        ("month", "12", "0.00"),
        ("quarter", "1", "300.00"),
        ("quarter", "2", "0.00"),
        ("department", None, "100.00"),
        ("portfolio", None, "100.00"),
        ("project", None, "100.00"),
        ("coordination", None, "100.00"),
        ("contract", None, "100.00"),
        ("supplier", None, "100.00"),
        ("contract_status", "SUSPENDED", "200.00"),
        ("contract_status", "CLOSED", "0.00"),
        ("category", "CAPEX", "100.00"),
        ("category", "OPEX", "200.00"),
    ],
)
@override_settings(DEBUG=True)
def test_each_filter_limits_actual_financial_values(
    filter_data, field, value, expected
):
    user, year, scenarios = filter_data
    filters = {
        "year": str(year),
        field: str(scenarios[0][field]) if value is None else value,
    }
    result = dashboard(user, filters)
    assert result["committed"] == expected
    assert Decimal(result["realized"]) == Decimal(expected) / 2
    assert Decimal(result["paid"]) == Decimal(expected) / 4


@override_settings(DEBUG=True)
def test_year_without_data_and_incompatible_filters_return_zero(filter_data):
    user, year, scenarios = filter_data
    assert dashboard(user, {"year": str(year - 1)})["committed"] == "0.00"
    result = dashboard(
        user,
        {
            "year": str(year),
            "portfolio": str(scenarios[0]["portfolio"]),
            "project": str(scenarios[1]["project"]),
        },
    )
    assert result["committed"] == "0.00"


def test_decimal_year_returns_validation_error(filter_data):
    user, _, _ = filter_data
    client = APIClient()
    client.force_authenticate(user)
    assert client.get("/api/dashboard/?year=2026.05").status_code == 400
