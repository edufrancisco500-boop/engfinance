from decimal import Decimal, InvalidOperation, ROUND_DOWN
import hashlib
import json
from django.conf import settings
from django.db import transaction
from django.db.models import Sum, Max
from django.utils import timezone
from rest_framework.exceptions import ValidationError, PermissionDenied
from apps.registry.models import AuditEvent
from .access import require_departments
from .models import (
    Allocation,
    Amendment,
    Budget,
    BudgetRevision,
    Document,
    Funding,
    FundingItem,
    Parcel,
    ParcelLink,
    Policy,
    State,
    Transfer,
    PeriodChange,
)

ZERO = Decimal("0.00")
CENT = Decimal("0.01")


def money(value):
    try:
        result = Decimal(str(value))
        if (
            not result.is_finite()
            or abs(result) >= Decimal("10000000000000000")
            or result != result.quantize(CENT)
        ):
            raise InvalidOperation
        return result.quantize(CENT)
    except (InvalidOperation, ValueError, TypeError):
        raise ValidationError(
            "Informe valor monetário finito, com até duas casas decimais."
        )


def total(query, field="amount"):
    return query.aggregate(value=Sum(field))["value"] or ZERO


def audit(actor, action, obj, before=None):
    return AuditEvent.objects.create(
        actor=actor,
        action=action,
        resource=obj._meta.label,
        object_id=str(obj.pk),
        before=before or {},
        after={
            "status": getattr(obj, "status", ""),
            "reason": getattr(obj, "reason", ""),
        },
    )


def policy_lock():
    # Mutex financeiro explícito: garante consistência entre limites, versões e etapas.
    # Adequado ao MVP; particionar por fonte em escala exige manter a mesma ordem de bloqueios.
    policy = Policy.objects.select_for_update().order_by("pk").first()
    if policy is None:
        raise ValidationError("Política financeira ainda não configurada.")
    if policy.demo:
        if not settings.DEBUG:
            raise ValidationError(
                "Política de demonstração não pode operar fora do desenvolvimento."
            )
    elif not policy.approved_for_real_use:
        raise ValidationError(
            "A política financeira precisa de validação formal antes do uso real."
        )
    return policy


def budget_value(budget):
    return (budget.amount if budget.status == State.APPROVED else ZERO) + total(
        budget.revisions.filter(status=State.APPROVED)
    )


def contract_value(contract):
    return contract.original_value + total(
        contract.amendments.filter(status=State.APPROVED)
    )


def allocation_value(allocation):
    return (
        allocation.amount
        + total(allocation.transfers_in.filter(status=State.APPROVED))
        - total(allocation.transfers_out.filter(status=State.APPROVED))
    )


def net_parcels(query):
    query = query.filter(document__status=State.APPROVED)
    return total(query.filter(document__reversal_of__isnull=True)) - total(
        query.filter(document__reversal_of__isnull=False)
    )


def used(allocation, kind="COMMITMENT", contract=None):
    query = allocation.parcels.filter(document__kind=kind)
    if contract is not None:
        query = query.filter(document__contract=contract)
    return net_parcels(query)


def validate_allocation(allocation):
    dept = allocation.budget.portfolio.department_id
    if allocation.project_id and allocation.project.department_id != dept:
        raise ValidationError(
            "O projeto e a fonte orçamentária devem pertencer à mesma gerência nesta política."
        )
    if allocation.project_id and allocation.project.category not in (
        "MIXED",
        allocation.budget.category,
    ):
        raise ValidationError("Categoria da fonte incompatível com o projeto.")
    if allocation.cost_center_id and allocation.cost_center.department_id != dept:
        raise ValidationError("Centro de custo incompatível com a fonte orçamentária.")


def source_departments(obj):
    if isinstance(obj, PeriodChange):
        return set()
    if isinstance(obj, Budget):
        return {obj.portfolio.department_id}
    if isinstance(obj, (Allocation, BudgetRevision)):
        return {obj.budget.portfolio.department_id}
    if isinstance(obj, Transfer):
        return {
            obj.source.budget.portfolio.department_id,
            obj.target.budget.portfolio.department_id,
        }
    ids = {obj.contract.department_id}
    parts = (
        obj.parcels.all()
        if isinstance(obj, Document)
        else obj.items.all()
        if isinstance(obj, Funding)
        else []
    )
    ids.update(part.allocation.budget.portfolio.department_id for part in parts)
    return ids


def distribute(amount, items):
    """Entrada homogênea por valor ou percentual; centavos pelo maior resto."""
    if not items:
        raise ValidationError("Informe ao menos uma parcela.")
    if len({int(item["allocation"]) for item in items}) != len(items):
        raise ValidationError("Uma fonte não pode aparecer duas vezes no mesmo rateio.")
    percent_mode = all(
        "percent" in item and item["percent"] is not None for item in items
    )
    if percent_mode:
        try:
            weights = [Decimal(str(item["percent"])) for item in items]
            if (
                any(not w.is_finite() or w <= 0 or w > 100 for w in weights)
                or sum(weights) != 100
            ):
                raise ValueError
        except (InvalidOperation, ValueError):
            raise ValidationError("Percentuais positivos devem somar exatamente 100%.")
        raw = [amount * w / 100 for w in weights]
        values = [value.quantize(CENT, rounding=ROUND_DOWN) for value in raw]
        cents = int((amount - sum(values)) / CENT)
        order = sorted(
            range(len(items)),
            key=lambda i: (-(raw[i] - values[i]), int(items[i]["allocation"])),
        )
        for i in order[:cents]:
            values[i] += CENT
    else:
        if any("percent" in item and item["percent"] is not None for item in items):
            raise ValidationError(
                "Use somente valores ou somente percentuais por rateio."
            )
        values = [money(item.get("amount")) for item in items]
    if any(value <= 0 for value in values) or sum(values, ZERO) != amount:
        raise ValidationError(
            "Parcelas positivas devem totalizar exatamente o valor distribuído."
        )
    return [(int(item["allocation"]), value) for item, value in zip(items, values)]


@transaction.atomic
def create_split(*, model, actor, data, items, sources=()):
    policy_lock()
    amount = money(data["amount"])
    if amount <= 0:
        raise ValidationError("O valor deve ser positivo.")
    contract = data["contract"]
    require_departments(actor, {contract.department_id})
    if model is Document:
        fingerprint = hashlib.sha256(
            json.dumps(
                {
                    "data": {
                        k: str(getattr(v, "pk", v))
                        for k, v in data.items()
                        if k != "idempotency_key"
                    },
                    "items": items,
                    "sources": sorted(sources),
                },
                sort_keys=True,
                default=str,
            ).encode()
        ).hexdigest()
        key = data.get("idempotency_key")
        existing = Document.objects.filter(idempotency_key=key).first() if key else None
        if existing:
            require_departments(actor, source_departments(existing))
            if existing.created_by_id != actor.pk:
                raise PermissionDenied("Chave de idempotência já utilizada.")
            if existing.request_fingerprint != fingerprint:
                raise ValidationError(
                    "Chave de idempotência reutilizada com conteúdo diferente."
                )
            return existing
        data["request_fingerprint"] = fingerprint
        if data.get("funding"):
            funding = data["funding"]
            if funding.contract_id != contract.pk or funding.status != State.APPROVED:
                raise ValidationError("Rateio contratual incompatível ou não aprovado.")
            require_departments(actor, source_departments(funding))
            if not items:
                items = [
                    {
                        "allocation": i.allocation_id,
                        "percent": str(i.amount / funding.amount * 100),
                    }
                    for i in funding.items.order_by("allocation_id")
                ]
                # Usa pesos exatos em moeda para não acumular arredondamento de percentuais.
                base = list(funding.items.order_by("allocation_id"))
                raw = [amount * i.amount / funding.amount for i in base]
                vals = [v.quantize(CENT, rounding=ROUND_DOWN) for v in raw]
                for i in sorted(
                    range(len(base)),
                    key=lambda i: (-(raw[i] - vals[i]), base[i].allocation_id),
                )[: int((amount - sum(vals)) / CENT)]:
                    vals[i] += CENT
                items = [
                    {"allocation": i.allocation_id, "amount": str(v)}
                    for i, v in zip(base, vals)
                    if v > 0
                ]
    allocations = distribute(amount, items)
    for allocation_id, _ in allocations:
        try:
            allocation = Allocation.objects.select_related(
                "budget__portfolio", "project", "cost_center"
            ).get(pk=allocation_id)
        except Allocation.DoesNotExist:
            raise ValidationError("Fonte orçamentária não encontrada.")
        require_departments(actor, {allocation.budget.portfolio.department_id})
        if (
            allocation.status != State.APPROVED
            or allocation.budget.status != State.APPROVED
        ):
            raise ValidationError("A alocação e seu orçamento devem estar aprovados.")
        validate_allocation(allocation)
    if model is Funding:
        data["version"] = (
            Funding.objects.filter(contract=contract).aggregate(v=Max("version"))["v"]
            or 0
        ) + 1
    obj = model.objects.create(**data, created_by=actor)
    for allocation_id, value in allocations:
        if model is Funding:
            FundingItem.objects.create(
                funding=obj, allocation_id=allocation_id, amount=value
            )
        else:
            Parcel.objects.create(
                document=obj, allocation_id=allocation_id, amount=value
            )
    if model is Document:
        source_ids = set(sources)
        if obj.parent_id:
            source_ids.add(obj.parent_id)
        for source in Document.objects.filter(pk__in=source_ids):
            require_departments(actor, source_departments(source))
        if Document.objects.filter(pk__in=source_ids).count() != len(source_ids):
            raise ValidationError("Documento de origem não encontrado.")
        obj.sources.set(source_ids)
    audit(actor, "create", obj)
    return obj


def document_links(document):
    expected = {
        "MEASUREMENT": "COMMITMENT",
        "INVOICE": "MEASUREMENT",
        "PAYMENT": "INVOICE",
    }
    if document.kind == "COMMITMENT":
        if document.sources.exists():
            raise ValidationError(
                "Compromisso não deve ter documento financeiro anterior."
            )
        return
    sources = list(document.sources.order_by("pk"))
    if not sources:
        raise ValidationError("Informe os documentos aprovados da etapa anterior.")
    for source in sources:
        pending_or_done_reversal = Document.objects.filter(
            reversal_of=source,
            status__in=[State.DRAFT, State.SUBMITTED, State.APPROVED],
        ).exists()
        if (
            source.contract_id != document.contract_id
            or source.kind != expected[document.kind]
            or source.status != State.APPROVED
            or source.reversal_of_id
            or pending_or_done_reversal
        ):
            raise ValidationError(
                "Documento anterior incompatível, estornado ou não aprovado."
            )
    for target in document.parcels.all():
        remaining = target.amount
        for source in Parcel.objects.filter(
            document__in=sources, allocation=target.allocation
        ).order_by("pk"):
            consumed = total(
                source.outgoing_links.filter(
                    target__document__status=State.APPROVED
                ).exclude(target__document__reversal__status=State.APPROVED)
            )
            available = source.amount - consumed
            value = min(remaining, available)
            if value > 0:
                ParcelLink.objects.create(source=source, target=target, amount=value)
                remaining -= value
            if remaining == 0:
                break
        if remaining:
            raise ValidationError(
                "Valor ou fonte excede o saldo dos documentos anteriores. Reclassificações entre fontes exigem processo específico."
            )


@transaction.atomic
def transition(*, model, pk, actor, action, reason=""):
    policy = policy_lock()
    obj = model.objects.select_for_update().get(pk=pk)
    if isinstance(obj, PeriodChange) and not actor.has_perm("finance.change_policy"):
        raise PermissionDenied(
            "Encerramento e reabertura globais exigem administração financeira."
        )
    require_departments(actor, source_departments(obj))
    before = {"status": obj.status}
    if action == "submit":
        if obj.status != State.DRAFT:
            raise ValidationError("Somente rascunhos podem ser enviados.")
        obj.status = State.SUBMITTED
    elif action in ("approve", "reject"):
        if not actor.has_perm("finance.approve_finance"):
            raise PermissionDenied("Sem alçada de aprovação financeira.")
        if obj.status != State.SUBMITTED:
            raise ValidationError("A operação precisa estar em aprovação.")
        if obj.created_by_id == actor.pk and not (policy.demo and settings.DEBUG):
            raise ValidationError(
                "Solicitante e aprovador devem ser pessoas distintas."
            )
        if action == "reject":
            if not reason.strip():
                raise ValidationError("Informe o motivo da rejeição.")
            obj.reason += "\nRejeição: " + reason
            obj.status = State.REJECTED
        else:
            validate_approval(obj)
            obj.status = State.APPROVED
            obj.approved_by = actor
            obj.approved_at = timezone.now()
    else:
        raise ValidationError("Ação inválida.")
    obj.save()
    audit(actor, action, obj, before)
    return obj


def validate_approval(obj):
    if isinstance(obj, PeriodChange):
        if obj.month not in range(1, 13):
            raise ValidationError("Período inválido.")
    elif isinstance(obj, Budget):
        if obj.amount < 0:
            raise ValidationError("Orçamento inválido.")
    elif isinstance(obj, BudgetRevision):
        if obj.budget.status != State.APPROVED or budget_value(
            obj.budget
        ) + obj.amount < total(obj.budget.allocations.filter(status=State.APPROVED)):
            raise ValidationError(
                "A revisão exige orçamento aprovado e não pode reduzir recursos já alocados."
            )
    elif isinstance(obj, Allocation):
        validate_allocation(obj)
        if obj.budget.status != State.APPROVED or total(
            obj.budget.allocations.filter(status=State.APPROVED)
        ) + obj.amount > budget_value(obj.budget):
            raise ValidationError(
                "Alocação excede orçamento disponível. Aprove uma revisão formal primeiro."
            )
    elif isinstance(obj, Amendment):
        current = contract_value(obj.contract) + obj.amount
        committed = net_parcels(
            Parcel.objects.filter(
                document__contract=obj.contract, document__kind="COMMITMENT"
            )
        )
        if current < 0 or current < committed:
            raise ValidationError(
                "Aditivo reduz o contrato abaixo do valor já comprometido."
            )
    elif isinstance(obj, Transfer):
        if (
            obj.source_id == obj.target_id
            or obj.source.budget_id != obj.target.budget_id
        ):
            raise ValidationError(
                "Realocação exige fontes distintas do mesmo orçamento. Outras transferências exigem revisão formal."
            )
        if (
            obj.source.status != State.APPROVED
            or obj.target.status != State.APPROVED
            or obj.amount <= 0
        ):
            raise ValidationError(
                "Realocação exige alocações aprovadas e valor positivo."
            )
        if allocation_value(obj.source) - obj.amount < used(obj.source):
            raise ValidationError("Realocação consumiria recursos já comprometidos.")
    elif isinstance(obj, Funding):
        if total(obj.items.all()) != obj.amount or obj.amount > contract_value(
            obj.contract
        ):
            raise ValidationError(
                "Rateio deve totalizar a base e respeitar o valor contratual atualizado."
            )
        for item in obj.items.all():
            allocation = item.allocation
            if (
                allocation.status != State.APPROVED
                or allocation.budget.status != State.APPROVED
            ):
                raise ValidationError("Fonte não aprovada.")
            own = used(allocation, contract=obj.contract)
            other = used(allocation) - own
            if item.amount < own or item.amount + other > allocation_value(allocation):
                raise ValidationError(
                    "Rateio incompatível com compromissos existentes ou orçamento disponível."
                )
        included = obj.items.values("allocation_id")
        if net_parcels(
            Parcel.objects.filter(
                document__contract=obj.contract, document__kind="COMMITMENT"
            ).exclude(allocation_id__in=included)
        ):
            raise ValidationError(
                "Não é possível remover fonte com compromisso vigente."
            )
    elif isinstance(obj, Document):
        period = (
            PeriodChange.objects.filter(
                year=obj.date.year, month=obj.date.month, status=State.APPROVED
            )
            .order_by("-approved_at", "-pk")
            .first()
        )
        if period and period.closed:
            raise ValidationError(
                "Competência encerrada. Solicite reabertura formal antes de aprovar o lançamento ou estorno."
            )
        if total(obj.parcels.all()) != obj.amount:
            raise ValidationError("Parcelas divergentes do total do documento.")
        if obj.reversal_of_id:
            original = obj.reversal_of
            if original.status != State.APPROVED:
                raise ValidationError("Documento original não aprovado.")
            if (
                ParcelLink.objects.filter(
                    source__document=original, target__document__status=State.APPROVED
                )
                .exclude(target__document__reversal__status=State.APPROVED)
                .exists()
            ):
                raise ValidationError(
                    "Estorne primeiro os documentos posteriores que consumiram esta origem."
                )
            return
        if obj.kind == "COMMITMENT":
            current = net_parcels(
                Parcel.objects.filter(
                    document__contract=obj.contract, document__kind="COMMITMENT"
                )
            )
            if current + obj.amount > contract_value(obj.contract):
                raise ValidationError(
                    "Compromisso excede o valor contratual atualizado."
                )
            for part in obj.parcels.all():
                if used(part.allocation) + part.amount > allocation_value(
                    part.allocation
                ):
                    raise ValidationError(
                        "Compromisso excede o saldo disponível da alocação."
                    )
        for part in obj.parcels.all():
            if part.allocation.status != State.APPROVED:
                raise ValidationError("Fonte não aprovada.")
            if part.allocation.budget.year != obj.date.year:
                raise ValidationError(
                    "Exercício do documento difere da fonte. Transferência entre exercícios ainda requer política específica."
                )
        document_links(obj)


@transaction.atomic
def reverse(*, document, actor, reason):
    policy_lock()
    document = Document.objects.select_for_update().get(pk=document.pk)
    require_departments(actor, source_departments(document))
    existing = Document.objects.filter(reversal_of=document).first()
    if (
        document.status != State.APPROVED
        or document.reversal_of_id
        or existing
        and existing.status != State.REJECTED
    ):
        raise ValidationError(
            "Somente documentos aprovados e ainda não estornados podem ser revertidos."
        )
    if not reason.strip():
        raise ValidationError("Justifique o estorno.")
    if existing:
        previous = {
            "status": existing.status,
            "reason": existing.reason,
            "created_by": existing.created_by_id,
        }
        existing.status = State.DRAFT
        existing.reason = reason
        existing.created_by = actor
        existing.save(update_fields=["status", "reason", "created_by"])
        audit(actor, "request_reversal_again", existing, previous)
        return existing
    obj = Document.objects.create(
        contract=document.contract,
        kind=document.kind,
        reference=f"ESTORNO-{document.pk}",
        date=document.date,
        amount=document.amount,
        created_by=actor,
        reversal_of=document,
        reason=reason,
    )
    for parcel in document.parcels.all():
        Parcel.objects.create(
            document=obj, allocation=parcel.allocation, amount=parcel.amount
        )
    audit(actor, "request_reversal", obj)
    return obj
