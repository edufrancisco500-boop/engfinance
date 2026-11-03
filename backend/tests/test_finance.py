from datetime import date
from decimal import Decimal
import uuid
import pytest
from django.test import override_settings
from rest_framework.test import APIClient
from rest_framework.exceptions import ValidationError
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
    Funding,
    State,
)
from apps.finance.services import (
    create_split,
    transition,
    reverse,
    net_parcels,
    distribute,
)
from apps.finance.selectors import dashboard

pytestmark = pytest.mark.django_db


@pytest.fixture
def finance():
    actor = User.objects.create_superuser(username="finance-owner", password="test")
    Policy.objects.create(name="Teste", demo=True)
    dept = Department.objects.create(code="D", name="D")
    supplier = Supplier.objects.create(code="S", name="S", tax_id="99000000000100")
    contract = Contract.objects.create(
        code="C",
        name="C",
        department=dept,
        supplier=supplier,
        original_value=Decimal("1000"),
    )
    allocations = []
    for i in range(2):
        p = Portfolio.objects.create(code=f"P{i}", name=f"P{i}", department=dept)
        b = Budget.objects.create(
            portfolio=p,
            year=date.today().year,
            category="CAPEX",
            amount=1000,
            status="APPROVED",
            created_by=actor,
            reason="Teste",
        )
        a = Allocation.objects.create(
            budget=b, amount=800, status="APPROVED", created_by=actor, reason="Teste"
        )
        allocations.append(a)
    return actor, contract, allocations


def approve(obj, actor):
    transition(model=type(obj), pk=obj.pk, actor=actor, action="submit")
    transition(model=type(obj), pk=obj.pk, actor=actor, action="approve")
    obj.refresh_from_db()
    return obj


def document(
    actor, contract, allocations, kind="COMMITMENT", amount="600", sources=(), key=None
):
    data = {
        "contract": contract,
        "kind": kind,
        "amount": amount,
        "date": date.today(),
        "reference": str(uuid.uuid4()),
        "reason": "Teste",
    }
    if key:
        data["idempotency_key"] = key
    return create_split(
        model=Document,
        actor=actor,
        data=data,
        items=[
            {"allocation": a.pk, "percent": str(100 // len(allocations))}
            for a in allocations
        ],
        sources=sources,
    )


@override_settings(DEBUG=True)
def test_split_pipeline_and_reversals_do_not_double_count(finance):
    actor, contract, allocations = finance
    commitment = approve(document(actor, contract, allocations), actor)
    measure = approve(
        document(actor, contract, allocations, "MEASUREMENT", "300", [commitment.pk]),
        actor,
    )
    invoice = approve(
        document(actor, contract, allocations, "INVOICE", "200", [measure.pk]), actor
    )
    payment = approve(
        document(actor, contract, allocations, "PAYMENT", "100", [invoice.pk]), actor
    )
    result = dashboard(actor, {})
    assert result["committed"] == "600.00"
    assert result["realized"] == "300.00"
    assert result["paid"] == "100.00"
    assert sum(Decimal(p["committed"]) for p in result["portfolios"]) == Decimal("600")
    rev = reverse(document=measure, actor=actor, reason="Correção")
    transition(model=Document, pk=rev.pk, actor=actor, action="submit")
    with pytest.raises(ValidationError):
        transition(model=Document, pk=rev.pk, actor=actor, action="approve")
    assert net_parcels(Parcel.objects.filter(document__kind="MEASUREMENT")) == Decimal(
        "300"
    )
    approve(reverse(document=payment, actor=actor, reason="Pagamento incorreto"), actor)
    assert dashboard(actor, {})["paid"] == "0.00"
    # Um estorno em rascunho não libera o saldo de outro documento.
    with pytest.raises(ValidationError):
        approve(
            document(actor, contract, allocations, "INVOICE", "200", [measure.pk]),
            actor,
        )


@override_settings(DEBUG=True)
def test_overallocation_and_overcommitment_are_blocked(finance):
    actor, contract, allocations = finance
    excess = Allocation.objects.create(
        budget=allocations[0].budget, amount=300, created_by=actor, reason="Sem saldo"
    )
    with pytest.raises(ValidationError):
        approve(excess, actor)
    approve(document(actor, contract, allocations, amount="900"), actor)
    with pytest.raises(ValidationError):
        approve(document(actor, contract, allocations, amount="200"), actor)


@override_settings(DEBUG=True)
def test_document_idempotency_rejects_changed_payload(finance):
    actor, contract, allocations = finance
    key = uuid.uuid4()
    data = {
        "contract": contract,
        "kind": "COMMITMENT",
        "amount": "100",
        "date": date.today(),
        "reference": "IDEMPOTENT",
        "reason": "Teste",
        "idempotency_key": key,
    }
    items = [{"allocation": allocations[0].pk, "amount": "100"}]
    first = create_split(model=Document, actor=actor, data=dict(data), items=items)
    second = create_split(model=Document, actor=actor, data=dict(data), items=items)
    assert first.pk == second.pk
    data["amount"] = "101"
    with pytest.raises(ValidationError):
        create_split(model=Document, actor=actor, data=data, items=items)


@override_settings(DEBUG=True)
def test_versioned_funding_does_not_add_to_execution_and_document_can_override(finance):
    actor, contract, allocations = finance
    for weights in [("60", "40"), ("70", "30")]:
        funding = create_split(
            model=Funding,
            actor=actor,
            data={
                "contract": contract,
                "amount": "1000",
                "reason": "Rateio versionado",
            },
            items=[
                {"allocation": a.pk, "percent": w} for a, w in zip(allocations, weights)
            ],
        )
        approve(funding, actor)
    assert Funding.objects.filter(contract=contract, status=State.APPROVED).count() == 2
    assert dashboard(actor, {})["committed"] == "0.00"
    doc = create_split(
        model=Document,
        actor=actor,
        data={
            "contract": contract,
            "kind": "COMMITMENT",
            "amount": "400",
            "date": date.today(),
            "reference": "RATEIO-ESPECIFICO",
            "reason": "Documento com distribuição específica",
            "funding": funding,
        },
        items=[
            {"allocation": allocations[0].pk, "percent": "20"},
            {"allocation": allocations[1].pk, "percent": "80"},
        ],
    )
    approve(doc, actor)
    assert list(
        doc.parcels.order_by("allocation_id").values_list("amount", flat=True)
    ) == [Decimal("80"), Decimal("320")]
    assert dashboard(actor, {})["committed"] == "400.00"


@override_settings(DEBUG=False)
def test_demo_cannot_approve_in_production(finance):
    actor, contract, allocations = finance
    with pytest.raises(ValidationError):
        document(actor, contract, allocations)


@override_settings(DEBUG=True)
def test_rateio_rounding_and_hidden_source(finance):
    actor, contract, allocations = finance
    assert distribute(
        Decimal("0.05"),
        [{"allocation": 2, "percent": "50"}, {"allocation": 1, "percent": "50"}],
    ) == [(2, Decimal(".02")), (1, Decimal(".03"))]
    hidden = Department.objects.create(code="H", name="H")
    allocations[1].budget.portfolio.department = hidden
    allocations[1].budget.portfolio.save()
    user = User.objects.create_user(username="limited")
    DepartmentAccess.objects.create(user=user, department=contract.department)
    from django.contrib.auth.models import Permission

    user.user_permissions.add(Permission.objects.get(codename="view_document"))
    obj = approve(document(actor, contract, allocations), actor)
    client = APIClient()
    client.force_authenticate(user)
    assert client.get("/api/v1/documents/").json()["count"] == 0
    assert client.get(f"/api/v1/documents/{obj.pk}/").status_code == 404


@override_settings(DEBUG=True)
def test_api_idempotency_and_approval_workflow(finance):
    actor, contract, allocations = finance
    client = APIClient()
    client.force_authenticate(actor)
    payload = {
        "contract": contract.pk,
        "kind": "COMMITMENT",
        "amount": "100.00",
        "date": date.today().isoformat(),
        "reference": "API-TEST",
        "reason": "Teste API",
        "idempotency_key": str(uuid.uuid4()),
        "split": [{"allocation": allocations[0].pk, "percent": "100"}],
    }
    first = client.post("/api/v1/documents/", payload, format="json")
    assert first.status_code == 201, first.data
    again = client.post("/api/v1/documents/", payload, format="json")
    assert again.status_code == 201, again.data
    assert first.data["id"] == again.data["id"]
    url = f"/api/v1/documents/{first.data['id']}"
    assert client.post(url + "/submit/").status_code == 200
    assert client.post(url + "/approve/").status_code == 200
    assert client.patch(url + "/", {"amount": "1"}, format="json").status_code == 405
    assert client.delete(url + "/").status_code == 405


@override_settings(DEBUG=True)
def test_closed_period_blocks_document_approval(finance):
    from apps.finance.models import PeriodChange

    actor, contract, allocations = finance
    period = PeriodChange.objects.create(
        year=date.today().year,
        month=date.today().month,
        closed=True,
        created_by=actor,
        reason="Encerramento",
    )
    approve(period, actor)
    doc = document(actor, contract, allocations)
    transition(model=Document, pk=doc.pk, actor=actor, action="submit")
    with pytest.raises(ValidationError):
        transition(model=Document, pk=doc.pk, actor=actor, action="approve")
    reopen = PeriodChange.objects.create(
        year=date.today().year,
        month=date.today().month,
        closed=False,
        created_by=actor,
        reason="Reabertura",
    )
    approve(reopen, actor)
    transition(model=Document, pk=doc.pk, actor=actor, action="approve")


@override_settings(DEBUG=True)
def test_aggregate_filters_do_not_reset_annual_available_balance(finance):
    actor, contract, allocations = finance
    approve(document(actor, contract, allocations, amount="600"), actor)
    other_month = 1 if date.today().month != 1 else 2
    result = dashboard(
        actor, {"year": str(date.today().year), "month": str(other_month)}
    )
    assert result["committed"] == "0.00"
    assert result["available"] == "1400.00"


@pytest.mark.django_db(transaction=True)
@override_settings(DEBUG=True)
def test_concurrent_approvals_cannot_spend_same_balance(finance):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    from django.db import connection, connections

    if connection.vendor != "postgresql":
        pytest.skip("Bloqueios exigem PostgreSQL real.")
    actor, contract, allocations = finance
    contract.original_value = 2000
    contract.save()
    docs = [document(actor, contract, allocations[:1], amount="600") for _ in range(2)]
    for doc in docs:
        transition(model=Document, pk=doc.pk, actor=actor, action="submit")
    barrier = Barrier(2)

    def worker(pk):
        try:
            user = User.objects.get(pk=actor.pk)
            barrier.wait(timeout=10)
            try:
                transition(model=Document, pk=pk, actor=user, action="approve")
                return "approved"
            except ValidationError:
                return "blocked"
        finally:
            connections.close_all()

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(worker, [d.pk for d in docs]))
    assert sorted(results) == ["approved", "blocked"]
    assert net_parcels(Parcel.objects.filter(allocation=allocations[0])) == Decimal(
        "600"
    )
