import uuid
from decimal import Decimal
from django.conf import settings
from django.db import models
from django.db.models import Q
from django.core.validators import MinValueValidator


class Category(models.TextChoices):
    CAPEX = "CAPEX", "CAPEX"
    OPEX = "OPEX", "OPEX"


class State(models.TextChoices):
    DRAFT = "DRAFT", "Rascunho"
    SUBMITTED = "SUBMITTED", "Em aprovação"
    APPROVED = "APPROVED", "Aprovado"
    REJECTED = "REJECTED", "Rejeitado"


class Policy(models.Model):
    name = models.CharField(max_length=160)
    demo = models.BooleanField(default=True)
    approved_for_real_use = models.BooleanField(default=False)
    low_balance_percent = models.PositiveSmallIntegerField(default=15)
    poor_rating = models.DecimalField(max_digits=3, decimal_places=2, default=3)
    expiry_days = models.PositiveSmallIntegerField(default=60)
    explanation = models.TextField(
        default="Demonstração: realizado por medição aprovada; rateio contratual é planejamento, sem reserva automática."
    )

    class Meta:
        permissions = [
            ("approve_finance", "Aprovar operações financeiras"),
            ("view_analytics", "Consultar indicadores e relatórios"),
        ]


class Operation(models.Model):
    status = models.CharField(
        max_length=12, choices=State.choices, default=State.DRAFT, db_index=True
    )
    reason = models.TextField()
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+"
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="+",
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    approved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        abstract = True
        ordering = ["-created_at", "-pk"]


class Budget(Operation):
    portfolio = models.ForeignKey("registry.Portfolio", on_delete=models.PROTECT)
    year = models.PositiveIntegerField()
    category = models.CharField(max_length=5, choices=Category.choices)
    amount = models.DecimalField(
        max_digits=18, decimal_places=2, validators=[MinValueValidator(0)]
    )

    class Meta(Operation.Meta):
        constraints = [
            models.UniqueConstraint(
                fields=["portfolio", "year", "category"], name="unique_budget_source"
            ),
            models.CheckConstraint(
                condition=Q(amount__gte=0), name="budget_nonnegative"
            ),
        ]


class PeriodChange(Operation):
    year = models.PositiveIntegerField()
    month = models.PositiveSmallIntegerField()
    closed = models.BooleanField(default=True)

    class Meta(Operation.Meta):
        constraints = [
            models.CheckConstraint(
                condition=Q(month__gte=1, month__lte=12), name="valid_period_month"
            )
        ]


class BudgetRevision(Operation):
    budget = models.ForeignKey(
        Budget, on_delete=models.PROTECT, related_name="revisions"
    )
    amount = models.DecimalField(max_digits=18, decimal_places=2)


class Allocation(Operation):
    budget = models.ForeignKey(
        Budget, on_delete=models.PROTECT, related_name="allocations"
    )
    project = models.ForeignKey(
        "registry.Project", on_delete=models.PROTECT, null=True, blank=True
    )
    cost_center = models.ForeignKey(
        "registry.CostCenter", on_delete=models.PROTECT, null=True, blank=True
    )
    amount = models.DecimalField(
        max_digits=18, decimal_places=2, validators=[MinValueValidator(Decimal("0.01"))]
    )

    class Meta(Operation.Meta):
        constraints = [
            models.CheckConstraint(
                condition=Q(amount__gt=0), name="allocation_positive"
            )
        ]


class Amendment(Operation):
    contract = models.ForeignKey(
        "registry.Contract", on_delete=models.PROTECT, related_name="amendments"
    )
    amount = models.DecimalField(max_digits=18, decimal_places=2)
    end_date = models.DateField(null=True, blank=True)


class Transfer(Operation):
    source = models.ForeignKey(
        Allocation, on_delete=models.PROTECT, related_name="transfers_out"
    )
    target = models.ForeignKey(
        Allocation, on_delete=models.PROTECT, related_name="transfers_in"
    )
    amount = models.DecimalField(max_digits=18, decimal_places=2)

    class Meta(Operation.Meta):
        constraints = [
            models.CheckConstraint(condition=Q(amount__gt=0), name="transfer_positive"),
            models.CheckConstraint(
                condition=~Q(source=models.F("target")),
                name="transfer_different_sources",
            ),
        ]


class Funding(Operation):
    contract = models.ForeignKey(
        "registry.Contract", on_delete=models.PROTECT, related_name="fundings"
    )
    version = models.PositiveIntegerField()
    amount = models.DecimalField(
        max_digits=18, decimal_places=2, validators=[MinValueValidator(Decimal("0.01"))]
    )

    class Meta(Operation.Meta):
        constraints = [
            models.UniqueConstraint(
                fields=["contract", "version"], name="unique_funding_version"
            ),
            models.CheckConstraint(condition=Q(amount__gt=0), name="funding_positive"),
        ]


class FundingItem(models.Model):
    funding = models.ForeignKey(Funding, on_delete=models.PROTECT, related_name="items")
    allocation = models.ForeignKey(Allocation, on_delete=models.PROTECT)
    amount = models.DecimalField(max_digits=18, decimal_places=2)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["funding", "allocation"], name="unique_funding_source"
            ),
            models.CheckConstraint(
                condition=Q(amount__gt=0), name="funding_item_positive"
            ),
        ]


class Document(Operation):
    class Kind(models.TextChoices):
        COMMITMENT = "COMMITMENT", "Compromisso"
        MEASUREMENT = "MEASUREMENT", "Medição"
        INVOICE = "INVOICE", "Nota fiscal"
        PAYMENT = "PAYMENT", "Pagamento"

    idempotency_key = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    request_fingerprint = models.CharField(max_length=64, blank=True)
    contract = models.ForeignKey(
        "registry.Contract",
        on_delete=models.PROTECT,
        related_name="financial_documents",
    )
    kind = models.CharField(max_length=12, choices=Kind.choices, db_index=True)
    reference = models.CharField(max_length=120)
    date = models.DateField(db_index=True)
    amount = models.DecimalField(max_digits=18, decimal_places=2)
    funding = models.ForeignKey(
        Funding, on_delete=models.PROTECT, null=True, blank=True
    )
    reversal_of = models.OneToOneField(
        "self", on_delete=models.PROTECT, null=True, blank=True, related_name="reversal"
    )
    parent = models.ForeignKey(
        "self", on_delete=models.PROTECT, null=True, blank=True, related_name="children"
    )
    sources = models.ManyToManyField(
        "self", symmetrical=False, blank=True, related_name="derived_documents"
    )

    class Meta(Operation.Meta):
        constraints = [
            models.UniqueConstraint(
                fields=["contract", "kind", "reference"],
                name="unique_document_reference",
            ),
            models.CheckConstraint(condition=Q(amount__gt=0), name="document_positive"),
        ]


class Parcel(models.Model):
    document = models.ForeignKey(
        Document, on_delete=models.PROTECT, related_name="parcels"
    )
    allocation = models.ForeignKey(
        Allocation, on_delete=models.PROTECT, related_name="parcels"
    )
    amount = models.DecimalField(max_digits=18, decimal_places=2)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["document", "allocation"], name="unique_document_source"
            ),
            models.CheckConstraint(condition=Q(amount__gt=0), name="parcel_positive"),
        ]


class Attachment(models.Model):
    contract = models.ForeignKey(
        "registry.Contract", on_delete=models.PROTECT, related_name="attachments"
    )
    name = models.CharField(max_length=180)
    file = models.FileField(upload_to="private/contracts/%Y/%m/")
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)


class ContractUsage(models.Model):
    contract = models.ForeignKey(
        "registry.Contract", on_delete=models.PROTECT, related_name="usage_records"
    )
    project = models.ForeignKey(
        "registry.Project", on_delete=models.PROTECT, null=True, blank=True
    )
    person_name = models.CharField(max_length=150)
    team = models.CharField(max_length=150, blank=True)
    date = models.DateField(db_index=True)
    purpose = models.TextField()
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date", "-pk"]


class ParcelLink(models.Model):
    source = models.ForeignKey(
        Parcel, on_delete=models.PROTECT, related_name="outgoing_links"
    )
    target = models.ForeignKey(
        Parcel, on_delete=models.PROTECT, related_name="incoming_links"
    )
    amount = models.DecimalField(max_digits=18, decimal_places=2)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["source", "target"], name="unique_parcel_link"
            ),
            models.CheckConstraint(condition=Q(amount__gt=0), name="link_positive"),
        ]
