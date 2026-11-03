from rest_framework.exceptions import PermissionDenied
from django.db.models import Q
from apps.registry.models import DepartmentAccess
from .models import (
    Allocation,
    Amendment,
    Attachment,
    Budget,
    BudgetRevision,
    Document,
    Funding,
    Transfer,
    PeriodChange,
    ContractUsage,
)


def department_ids(user):
    return DepartmentAccess.objects.filter(user=user).values_list(
        "department_id", flat=True
    )


def require_departments(user, ids):
    if not user.is_superuser and not set(ids).issubset(set(department_ids(user))):
        raise PermissionDenied("Recurso fora do seu escopo de gerências.")


def scoped(query, user):
    if user.is_superuser:
        return query
    allowed = department_ids(user)
    model = query.model
    if model is PeriodChange:
        return query if user.has_perm("finance.view_periodchange") else query.none()
    if model is Budget:
        return query.filter(portfolio__department_id__in=allowed)
    if model in (Allocation, BudgetRevision):
        return query.filter(budget__portfolio__department_id__in=allowed)
    if model is Transfer:
        return query.filter(
            source__budget__portfolio__department_id__in=allowed,
            target__budget__portfolio__department_id__in=allowed,
        )
    if model in (Amendment, Attachment, ContractUsage):
        if model is ContractUsage:
            return query.filter(contract__department_id__in=allowed).filter(
                Q(project__isnull=True) | Q(project__department_id__in=allowed)
            )
        return query.filter(contract__department_id__in=allowed)
    if model in (Document, Funding):
        # Excluir por parcela, não por queryset multivalorado: um rateio pode conter fontes visíveis e ocultas.
        from .models import Parcel, FundingItem

        parts = Parcel if model is Document else FundingItem
        fk = "document_id" if model is Document else "funding_id"
        hidden_ids = parts.objects.exclude(
            allocation__budget__portfolio__department_id__in=allowed
        ).values(fk)
        return query.filter(contract__department_id__in=allowed).exclude(
            pk__in=hidden_ids
        )
    raise ValueError("Modelo sem regra de escopo.")
