from decimal import Decimal
from django.db.models import Avg, Count, Q
from django.utils import timezone
from django.db import transaction
from rest_framework.exceptions import PermissionDenied, ValidationError
from apps.registry.models import Contract, Portfolio, Project
from apps.evaluations.models import Answer, Evaluation, Invitation
from .access import department_ids, scoped
from .models import (
    Allocation,
    Budget,
    Document,
    Funding,
    Parcel,
    Policy,
    State,
    ContractUsage,
)
from .contract_analytics import contract_metrics, rankings, percentage
from .services import (
    ZERO,
    allocation_value,
    budget_value,
    contract_value,
    net_parcels,
    total,
)


def filter_params(params):
    result = {}
    for key in (
        "year",
        "month",
        "quarter",
        "department",
        "portfolio",
        "project",
        "contract",
        "supplier",
        "coordination",
    ):
        value = params.get(key)
        if value not in ("", None):
            try:
                result[key] = int(value)
            except (TypeError, ValueError):
                raise ValidationError(f"Filtro {key} inválido.")
    if "year" in result and not 1900 <= result["year"] <= 9999:
        raise ValidationError(
            "Ano inválido. Selecione um ano inteiro entre 1900 e 9999."
        )
    if result.get("month", 1) not in range(1, 13) or result.get(
        "quarter", 1
    ) not in range(1, 5):
        raise ValidationError("Período inválido.")
    if params.get("category"):
        if params["category"] not in ("CAPEX", "OPEX"):
            raise ValidationError("Categoria inválida.")
        result["category"] = params["category"]
    if params.get("contract_status"):
        if params["contract_status"] not in (
            "DRAFT",
            "ACTIVE",
            "SUSPENDED",
            "CLOSED",
            "CANCELLED",
        ):
            raise ValidationError("Status contratual inválido.")
        result["contract_status"] = params["contract_status"]
    return result


def data_scope(user, params):
    if not user.has_perm("finance.view_analytics"):
        raise PermissionDenied("Sem acesso a indicadores e relatórios.")
    filters = filter_params(params)
    budgets = scoped(Budget.objects.filter(status=State.APPROVED), user)
    allocations = scoped(Allocation.objects.filter(status=State.APPROVED), user)
    documents = scoped(Document.objects.filter(status=State.APPROVED), user)
    for key, value in filters.items():
        budget_key = {
            "year": "year",
            "category": "category",
            "department": "portfolio__department_id",
            "portfolio": "portfolio_id",
        }.get(key)
        if budget_key:
            budgets = budgets.filter(**{budget_key: value})
            allocations = allocations.filter(**{f"budget__{budget_key}": value})
        if key == "project":
            allocations = allocations.filter(project_id=value)
        if key == "coordination":
            allocations = allocations.filter(project__coordination_id=value)
        document_key = {
            "year": "date__year",
            "month": "date__month",
            "contract": "contract_id",
            "supplier": "contract__supplier_id",
            "contract_status": "contract__status",
        }.get(key)
        if document_key:
            documents = documents.filter(**{document_key: value})
        if key == "quarter":
            documents = documents.filter(date__quarter=value)
    parcels = Parcel.objects.filter(document__in=documents, allocation__in=allocations)
    if any(k in filters for k in ("contract", "supplier", "contract_status")):
        relevant_contracts = Contract.objects.all()
        if "contract" in filters:
            relevant_contracts = relevant_contracts.filter(pk=filters["contract"])
        if "supplier" in filters:
            relevant_contracts = relevant_contracts.filter(
                supplier_id=filters["supplier"]
            )
        if "contract_status" in filters:
            relevant_contracts = relevant_contracts.filter(
                status=filters["contract_status"]
            )
        funds = scoped(
            Funding.objects.filter(
                status=State.APPROVED, contract__in=relevant_contracts
            ),
            user,
        )
        allocations = allocations.filter(
            Q(pk__in=funds.values("items__allocation_id"))
            | Q(
                pk__in=Parcel.objects.filter(
                    document__in=scoped(
                        Document.objects.filter(
                            status=State.APPROVED, contract__in=relevant_contracts
                        ),
                        user,
                    )
                ).values("allocation_id")
            )
        ).distinct()
        parcels = parcels.filter(allocation__in=allocations)
        budgets = budgets.filter(pk__in=allocations.values("budget_id"))
    if "project" in filters or "coordination" in filters:
        budgets = budgets.filter(pk__in=allocations.values("budget_id"))
    return filters, budgets, allocations, documents, parcels


def evaluation_results(user, filters, contract_ids=None):
    if not user.has_perm("evaluations.view_results"):
        return {
            "average": None,
            "responses": 0,
            "invited": 0,
            "participation": None,
            "criteria": [],
            "quarterly": [],
            "contracts": [],
        }
    invites = Invitation.objects.all()
    if not user.is_superuser:
        invites = invites.filter(contract__department_id__in=department_ids(user))
    if contract_ids is not None:
        invites = invites.filter(contract_id__in=contract_ids)
    for key, field in {
        "year": "cycle__year",
        "quarter": "cycle__quarter",
        "department": "contract__department_id",
        "contract": "contract_id",
        "supplier": "contract__supplier_id",
    }.items():
        if key in filters:
            invites = invites.filter(**{field: filters[key]})
    answers = Answer.objects.filter(evaluation__invitation__in=invites)
    count = Evaluation.objects.filter(invitation__in=invites).count()
    invited = invites.count()
    policy = Policy.objects.order_by("pk").first()
    threshold = 1 if policy and policy.demo else 3
    safe = count >= threshold
    criteria = (
        list(
            answers.values("criterion__name").annotate(
                average=Avg("score"), responses=Count("score")
            )
        )
        if safe
        else []
    )
    quarter_groups = list(
        answers.values(
            "evaluation__invitation__cycle__year",
            "evaluation__invitation__cycle__quarter",
        )
        .annotate(average=Avg("score"), responses=Count("evaluation", distinct=True))
        .filter(responses__gte=threshold)
    )
    contract_groups = list(
        answers.values(
            "evaluation__invitation__contract_id",
            "evaluation__invitation__contract__name",
        )
        .annotate(average=Avg("score"), responses=Count("evaluation", distinct=True))
        .filter(responses__gte=threshold)
    )
    return {
        "average": answers.aggregate(v=Avg("score"))["v"] if safe else None,
        "responses": count,
        "invited": invited,
        "participation": round(count / invited * 100, 1) if invited else None,
        "criteria": criteria,
        "quarterly": quarter_groups,
        "contracts": contract_groups,
        "minimum_responses": threshold,
    }


@transaction.atomic
def dashboard(user, params):
    if not user.has_perm("finance.view_analytics"):
        raise PermissionDenied("Sem acesso a indicadores e relatórios.")
    Policy.objects.select_for_update().order_by("pk").first()
    filters, budgets, allocations, documents, parcels = data_scope(user, params)
    stock_params = {k: v for k, v in params.items() if k not in ("month", "quarter")}
    _, _, _, _, stock_parcels = data_scope(user, stock_params)
    lifetime_params = {
        k: v for k, v in params.items() if k not in ("year", "month", "quarter")
    }
    _, _, lifetime_allocations, _, lifetime_parcels = data_scope(user, lifetime_params)
    usage = scoped(ContractUsage.objects.all(), user)
    for key, field in {
        "year": "date__year",
        "month": "date__month",
        "quarter": "date__quarter",
        "project": "project_id",
        "coordination": "project__coordination_id",
    }.items():
        if key in filters:
            usage = usage.filter(**{field: filters[key]})
    policy = Policy.objects.order_by("pk").first()
    money_totals = {
        kind: net_parcels(parcels.filter(document__kind=kind))
        for kind in Document.Kind.values
    }
    # Orçamento de fontes compartilhadas não é atribuído integralmente a um contrato/projeto.
    narrowed = any(
        key in filters
        for key in (
            "project",
            "contract",
            "supplier",
            "coordination",
            "contract_status",
        )
    )
    assigned = sum((allocation_value(a) for a in allocations), ZERO)
    approved_budget = sum((budget_value(b) for b in budgets), ZERO)
    base = assigned if narrowed else approved_budget
    portfolio_groups = []
    for portfolio in Portfolio.objects.filter(
        pk__in=budgets.values("portfolio_id")
    ).order_by("code"):
        source_allocations = allocations.filter(budget__portfolio=portfolio)
        source_parcels = parcels.filter(allocation__budget__portfolio=portfolio)
        source_stock = stock_parcels.filter(allocation__budget__portfolio=portfolio)
        budget_amount = (
            sum((allocation_value(a) for a in source_allocations), ZERO)
            if narrowed
            else sum(
                (budget_value(b) for b in budgets.filter(portfolio=portfolio)), ZERO
            )
        )
        portfolio_groups.append(
            {
                "id": portfolio.pk,
                "name": portfolio.name,
                "code": portfolio.code,
                "budget": str(budget_amount),
                "allocated": str(
                    sum((allocation_value(a) for a in source_allocations), ZERO)
                ),
                "committed": str(
                    net_parcels(source_parcels.filter(document__kind="COMMITMENT"))
                ),
                "realized": str(
                    net_parcels(source_parcels.filter(document__kind="MEASUREMENT"))
                ),
                "paid": str(
                    net_parcels(source_parcels.filter(document__kind="PAYMENT"))
                ),
                "available": str(
                    budget_amount
                    - net_parcels(source_stock.filter(document__kind="COMMITMENT"))
                ),
            }
        )
    monthly = []
    for month in range(1, 13):
        group = parcels.filter(document__date__month=month)
        monthly.append(
            {
                "month": month,
                "realized": str(
                    net_parcels(group.filter(document__kind="MEASUREMENT"))
                ),
                "paid": str(net_parcels(group.filter(document__kind="PAYMENT"))),
            }
        )
    categories = []
    for category in ("CAPEX", "OPEX"):
        group = parcels.filter(allocation__budget__category=category)
        budget_amount = (
            sum(
                (
                    allocation_value(a)
                    for a in allocations.filter(budget__category=category)
                ),
                ZERO,
            )
            if narrowed
            else sum((budget_value(b) for b in budgets.filter(category=category)), ZERO)
        )
        categories.append(
            {
                "name": category,
                "budget": str(budget_amount),
                "committed": str(
                    net_parcels(group.filter(document__kind="COMMITMENT"))
                ),
                "realized": str(
                    net_parcels(group.filter(document__kind="MEASUREMENT"))
                ),
                "paid": str(net_parcels(group.filter(document__kind="PAYMENT"))),
                "available": str(
                    budget_amount
                    - net_parcels(
                        stock_parcels.filter(
                            allocation__budget__category=category,
                            document__kind="COMMITMENT",
                        )
                    )
                ),
                "execution_percent": percentage(
                    net_parcels(group.filter(document__kind="MEASUREMENT")),
                    budget_amount,
                ),
            }
        )
    category_monthly = []
    for month in range(1, 13):
        row = {"month": month}
        for category in ("CAPEX", "OPEX"):
            row[category] = str(
                net_parcels(
                    parcels.filter(
                        document__date__month=month,
                        document__kind="MEASUREMENT",
                        allocation__budget__category=category,
                    )
                )
            )
        category_monthly.append(row)
    contracts = Contract.objects.all()
    projects = Project.objects.all()
    if not user.is_superuser:
        contracts = contracts.filter(department_id__in=department_ids(user))
        projects = projects.filter(department_id__in=department_ids(user))
    if filters.get("department"):
        contracts = contracts.filter(department_id=filters["department"])
        projects = projects.filter(department_id=filters["department"])
    if any(
        k in filters
        for k in (
            "portfolio",
            "project",
            "category",
            "contract",
            "supplier",
            "coordination",
            "contract_status",
        )
    ):
        funding_ids = scoped(
            Funding.objects.filter(
                status=State.APPROVED, items__allocation__in=allocations
            ),
            user,
        ).values("contract_id")
        ledger_ids = scoped(
            Document.objects.filter(
                status=State.APPROVED, parcels__allocation__in=allocations
            ),
            user,
        ).values("contract_id")
        contracts = contracts.filter(
            Q(pk__in=funding_ids) | Q(pk__in=ledger_ids)
        ).distinct()
        projects = projects.filter(pk__in=allocations.values("project_id")).distinct()
    if filters.get("contract"):
        contracts = contracts.filter(pk=filters["contract"])
    if filters.get("supplier"):
        contracts = contracts.filter(supplier_id=filters["supplier"])
    if filters.get("contract_status"):
        contracts = contracts.filter(status=filters["contract_status"])
    result_eval = evaluation_results(user, filters, contracts.values("pk"))
    ratings = {
        r["evaluation__invitation__contract_id"]: r["average"]
        for r in result_eval["contracts"]
    }
    alerts = []
    risks = []
    today = timezone.localdate()
    for contract in contracts.select_related("supplier"):
        group = lifetime_parcels.filter(
            document__contract=contract, document__date__lte=today
        )
        committed = net_parcels(group.filter(document__kind="COMMITMENT"))
        realized = net_parcels(group.filter(document__kind="MEASUREMENT"))
        funding = (
            scoped(
                Funding.objects.filter(contract=contract, status=State.APPROVED), user
            )
            .order_by("-version")
            .first()
        )
        narrowed_sources = any(
            key in filters
            for key in (
                "portfolio",
                "project",
                "category",
                "department",
                "coordination",
            )
        )
        updated = (
            total(funding.items.filter(allocation__in=lifetime_allocations))
            if narrowed_sources and funding
            else contract_value(contract)
        )
        balance = updated - committed
        rating = ratings.get(contract.pk)
        financial_risk = updated > 0 and balance / updated * 100 < (
            policy.low_balance_percent if policy else 15
        )
        poor = rating is not None and rating < float(
            policy.poor_rating if policy else 3
        )
        reasons = []
        expiry = contract.end_date
        amendment_end = (
            contract.amendments.filter(status=State.APPROVED, end_date__isnull=False)
            .order_by("-approved_at")
            .first()
        )
        if amendment_end:
            expiry = amendment_end.end_date
        if expiry:
            days = (expiry - today).days
            if days < 0:
                reasons.append("Contrato vencido")
            elif days <= (policy.expiry_days if policy else 60):
                reasons.append(f"Vence em {days} dias")
        if financial_risk:
            reasons.append("Saldo contratual reduzido")
        if poor:
            reasons.append("Avaliação abaixo do limite")
        if reasons:
            alerts.append(
                {
                    "contract": contract.pk,
                    "name": contract.name,
                    "reasons": reasons,
                    "severity": "high" if poor and financial_risk else "medium",
                }
            )
        detail = contract_metrics(
            contract=contract,
            value=updated,
            expiry=expiry,
            position=group,
            period=parcels.filter(document__contract=contract),
            today=today,
            usage=usage.filter(contract=contract),
            show_people=user.has_perm("finance.view_contractusage"),
        )
        risks.append(
            {
                "id": contract.pk,
                "name": contract.name,
                "value": str(updated),
                "committed": str(committed),
                "realized": str(realized),
                "paid": str(net_parcels(group.filter(document__kind="PAYMENT"))),
                "balance": str(balance),
                "consumption_percent": float(committed / updated * 100)
                if updated
                else 0,
                "rating": rating,
                "risk": "Alto"
                if financial_risk and poor
                else "Atenção"
                if financial_risk or poor
                else "Regular",
                **detail,
            }
        )
    project_rows = []
    for project in projects:
        group = parcels.filter(allocation__project=project)
        assigned_project = sum(
            (allocation_value(a) for a in allocations.filter(project=project)), ZERO
        )
        realized = net_parcels(group.filter(document__kind="MEASUREMENT"))
        execution = (
            float(realized / assigned_project * 100) if assigned_project else None
        )
        project_rows.append(
            {
                "id": project.pk,
                "name": project.name,
                "physical": str(project.physical_progress),
                "budget": str(assigned_project),
                "realized": str(realized),
                "financial": execution,
                "gap": float(project.physical_progress) - execution
                if execution is not None
                else None,
            }
        )
    denominator = (
        1
        if filters.get("month")
        else 3
        if filters.get("quarter")
        else today.month
        if filters.get("year") == today.year
        else 12
    )
    return {
        "policy": {
            "demo": policy.demo if policy else True,
            "name": policy.name if policy else "Não configurada",
            "explanation": policy.explanation if policy else "",
            "low_balance_percent": policy.low_balance_percent if policy else 15,
            "poor_rating": str(policy.poor_rating) if policy else "3",
            "expiry_days": policy.expiry_days if policy else 60,
        },
        "filters": filters,
        "budget_label": "Alocações das fontes relacionadas"
        if narrowed
        else "Orçamento vigente",
        "budget": str(base),
        "allocated": str(assigned),
        "committed": str(money_totals["COMMITMENT"]),
        "realized": str(money_totals["MEASUREMENT"]),
        "invoiced": str(money_totals["INVOICE"]),
        "paid": str(money_totals["PAYMENT"]),
        "available": str(
            base - net_parcels(stock_parcels.filter(document__kind="COMMITMENT"))
        ),
        "available_label": "Saldo para comprometer no exercício (não reduzido ao mês/trimestre)",
        "execution": float(money_totals["MEASUREMENT"] / base * 100) if base else None,
        "projects_count": projects.count(),
        "contracts_count": contracts.count(),
        "portfolios": portfolio_groups,
        "monthly": monthly,
        "categories": categories,
        "category_monthly": category_monthly,
        "contract_rankings": rankings(risks),
        "contract_summary": {
            "value": str(sum((Decimal(r["value"]) for r in risks), ZERO)),
            "period_realized": str(
                sum((Decimal(r["period_realized"]) for r in risks), ZERO)
            ),
            "period_paid": str(sum((Decimal(r["period_paid"]) for r in risks), ZERO)),
            "lifetime_committed": str(
                sum((Decimal(r["lifetime_committed"]) for r in risks), ZERO)
            ),
            "lifetime_paid": str(
                sum((Decimal(r["lifetime_paid"]) for r in risks), ZERO)
            ),
            "balance": str(sum((Decimal(r["balance"]) for r in risks), ZERO)),
            "balance_percent": percentage(
                sum((Decimal(r["balance"]) for r in risks), ZERO),
                sum((Decimal(r["value"]) for r in risks), ZERO),
            ),
            "expiring": sum(
                1
                for r in risks
                if r["days_remaining"] is not None
                and 0 <= r["days_remaining"] <= (policy.expiry_days if policy else 60)
            ),
            "expired": sum(
                1
                for r in risks
                if r["days_remaining"] is not None and r["days_remaining"] < 0
            ),
            "usage_events": sum(r["usage_count"] for r in risks),
            "forecast_risks": sum(
                1
                for r in risks
                if r["forecast"]["scenario"]
                in ("exhaustion_before_expiry", "limit_reached")
            ),
        },
        "alerts": alerts,
        "contracts": risks,
        "projects": project_rows,
        "evaluations": result_eval,
        "forecast": {
            "method": "Média mensal do realizado observado; cenário linear, sem obrigação financeira",
            "next_month": str(
                (money_totals["MEASUREMENT"] / denominator).quantize(Decimal("0.01"))
            ),
        },
    }
