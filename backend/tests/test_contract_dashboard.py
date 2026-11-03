from datetime import timedelta
from decimal import Decimal
from io import BytesIO
import pytest
from django.utils import timezone
from django.contrib.auth.models import Permission
from rest_framework.test import APIClient
from openpyxl import load_workbook
from apps.accounts.models import User
from apps.registry.models import (
    Department,
    DepartmentAccess,
    Portfolio,
    Supplier,
    Contract,
)
from apps.finance.models import (
    Budget,
    Allocation,
    Document,
    Parcel,
    Policy,
    ContractUsage,
    Amendment,
)
from apps.finance.selectors import dashboard

pytestmark = pytest.mark.django_db


@pytest.fixture
def contract_data():
    user = User.objects.create_superuser(username="contract-analyst", password="test")
    Policy.objects.create(name="Teste de contratos", demo=True)
    today = timezone.localdate()
    dept = Department.objects.create(code="D", name="Gerência")
    portfolio = Portfolio.objects.create(code="P", name="Carteira", department=dept)
    supplier = Supplier.objects.create(
        code="S", name="Fornecedor fictício", tax_id="99000000000100"
    )
    budget = Budget.objects.create(
        portfolio=portfolio,
        year=today.year,
        category="CAPEX",
        amount=10000,
        created_by=user,
        reason="Teste",
        status="APPROVED",
    )
    allocation = Allocation.objects.create(
        budget=budget, amount=9000, created_by=user, reason="Teste", status="APPROVED"
    )
    contracts = []
    amounts = [100, 500, 200, 0, 400, 300, 600]
    usage_counts = [0, 4, 2, 5, 1, 3, 6]
    for index, (amount, usage_count) in enumerate(zip(amounts, usage_counts), 1):
        contract = Contract.objects.create(
            code=f"C{index}",
            name=f"Contrato {index}",
            department=dept,
            supplier=supplier,
            original_value=2000,
            status="ACTIVE",
            start_date=today - timedelta(days=90),
            end_date=today + timedelta(days=-5 if index == 6 else 300),
        )
        contracts.append(contract)
        for kind, value in [
            ("COMMITMENT", amount + 100),
            ("MEASUREMENT", amount),
            ("PAYMENT", amount / 2),
        ]:
            if not value:
                continue
            document = Document.objects.create(
                contract=contract,
                kind=kind,
                reference=f"{index}-{kind}",
                date=today,
                amount=Decimal(str(value)),
                reason="Teste",
                created_by=user,
                status="APPROVED",
            )
            Parcel.objects.create(
                document=document, allocation=allocation, amount=document.amount
            )
        for event in range(usage_count):
            ContractUsage.objects.create(
                contract=contract,
                person_name=f"Pessoa {index}",
                team="Equipe fictícia",
                date=today,
                purpose=f"Atividade {event}",
                created_by=user,
            )
    return user, dept, contracts, allocation


def test_top_five_spending_and_least_used_have_explicit_distinct_metrics(contract_data):
    user, _, contracts, _ = contract_data
    result = dashboard(user, {"year": str(timezone.localdate().year)})
    assert [row["code"] for row in result["contract_rankings"]["most_spent"]] == [
        "C7",
        "C2",
        "C5",
        "C6",
        "C3",
    ]
    assert [row["code"] for row in result["contract_rankings"]["least_used"]] == [
        "C1",
        "C5",
        "C3",
        "C6",
        "C2",
    ]
    c7 = next(row for row in result["contracts"] if row["code"] == "C7")
    assert c7["usage_count"] == 6
    assert c7["people_count"] == 1
    assert c7["people"][0]["uses"] == 6
    assert c7["people"][0]["name"] == "Pessoa 7"
    assert c7["start_year"] == contracts[-1].start_date.year
    assert c7["balance"] == "1300.00"
    assert c7["balance_percent"] == 65


def test_forecast_uses_approved_expiry_and_handles_no_spend_and_expired(contract_data):
    user, _, contracts, _ = contract_data
    today = timezone.localdate()
    Amendment.objects.create(
        contract=contracts[-1],
        amount=0,
        end_date=today + timedelta(days=400),
        status="APPROVED",
        approved_at=timezone.now(),
        created_by=user,
        reason="Extensão de prazo",
    )
    result = dashboard(user, {})
    rows = {row["code"]: row for row in result["contracts"]}
    assert rows["C7"]["days_remaining"] == 400
    assert rows["C7"]["end_date"] == (today + timedelta(days=400)).isoformat()
    assert rows["C7"]["forecast"]["scenario"] == "exhaustion_before_expiry"
    assert Decimal(rows["C7"]["forecast"]["projected_overrun"]) > 0
    assert rows["C4"]["forecast"]["scenario"] == "insufficient_data"
    assert rows["C4"]["forecast"]["exhaustion_date"] is None
    assert rows["C6"]["days_remaining"] == -5
    assert rows["C6"]["forecast"]["scenario"] == "expired"


def test_contract_balance_includes_prior_year_and_rankings_still_follow_period(
    contract_data,
):
    user, _, contracts, allocation = contract_data
    today = timezone.localdate()
    prior = today.replace(year=today.year - 1, month=1, day=1)
    document = Document.objects.create(
        contract=contracts[0],
        kind="COMMITMENT",
        reference="ANTERIOR",
        date=prior,
        amount=200,
        reason="Histórico",
        created_by=user,
        status="APPROVED",
    )
    Parcel.objects.create(document=document, allocation=allocation, amount=200)
    result = dashboard(user, {"year": str(today.year)})
    row = next(row for row in result["contracts"] if row["code"] == "C1")
    assert row["period_committed"] == "200.00"
    assert row["lifetime_committed"] == "400.00"
    assert row["balance"] == "1600.00"
    assert row["balance_percent"] == 80


def test_operational_names_need_specific_permission_and_excel_accepts_nested_details(
    contract_data,
):
    admin, dept, _, _ = contract_data
    user = User.objects.create_user(username="summary-reader")
    DepartmentAccess.objects.create(user=user, department=dept)
    user.user_permissions.add(Permission.objects.get(codename="view_analytics"))
    result = dashboard(user, {})
    assert any(row["people_count"] > 0 for row in result["contracts"])
    assert all(
        row["people"] == [] and not row["people_visible"] for row in result["contracts"]
    )
    client = APIClient()
    client.force_authenticate(admin)
    response = client.get("/api/reports/?section=contracts&format_file=xlsx")
    assert response.status_code == 200
    book = load_workbook(BytesIO(response.content))
    assert book.active.max_row == 10


def test_usage_api_checks_scope_and_rejects_future_usage(contract_data):
    admin, dept, contracts, _ = contract_data
    user = User.objects.create_user(username="usage-writer")
    user.user_permissions.add(Permission.objects.get(codename="add_contractusage"))
    client = APIClient()
    client.force_authenticate(user)
    payload = {
        "contract": contracts[0].pk,
        "person_name": "Pessoa fictícia",
        "date": timezone.localdate().isoformat(),
        "purpose": "Teste de uso",
    }
    assert (
        client.post("/api/v1/contract-usage/", payload, format="json").status_code
        == 403
    )
    DepartmentAccess.objects.create(user=user, department=dept)
    payload["date"] = (timezone.localdate() + timedelta(days=1)).isoformat()
    assert (
        client.post("/api/v1/contract-usage/", payload, format="json").status_code
        == 400
    )
    payload["date"] = timezone.localdate().isoformat()
    assert (
        client.post("/api/v1/contract-usage/", payload, format="json").status_code
        == 201
    )
