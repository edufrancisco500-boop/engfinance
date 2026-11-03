from django.conf import settings
from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator, RegexValidator


class NamedRecord(models.Model):
    code = models.CharField("Código", max_length=40, unique=True)
    name = models.CharField("Nome", max_length=180)
    description = models.TextField("Descrição", blank=True)
    active = models.BooleanField("Ativo", default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        abstract = True
        ordering = ["code"]

    def __str__(self):
        return f"{self.code} — {self.name}"


class Department(NamedRecord):
    pass


class Coordination(NamedRecord):
    department = models.ForeignKey(Department, on_delete=models.PROTECT)


class Portfolio(NamedRecord):
    department = models.ForeignKey(Department, on_delete=models.PROTECT)
    responsible = models.CharField(max_length=150, blank=True)


class Project(NamedRecord):
    department = models.ForeignKey(Department, on_delete=models.PROTECT)
    coordination = models.ForeignKey(
        Coordination, on_delete=models.PROTECT, null=True, blank=True
    )
    internal_order = models.CharField(max_length=80, blank=True)
    pep_element = models.CharField(max_length=80, blank=True)
    category = models.CharField(
        max_length=5,
        choices=[("CAPEX", "CAPEX"), ("OPEX", "OPEX"), ("MIXED", "Misto")],
        default="MIXED",
    )
    status = models.CharField(
        max_length=12,
        choices=[
            ("PLANNED", "Planejado"),
            ("ACTIVE", "Em execução"),
            ("PAUSED", "Pausado"),
            ("COMPLETED", "Concluído"),
            ("CANCELLED", "Cancelado"),
        ],
        default="PLANNED",
    )
    responsible = models.CharField(max_length=150, blank=True)
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    physical_progress = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
    )
    # Fontes de financiamento serão associadas por alocações, não por FK exclusiva.


class Supplier(NamedRecord):
    tax_id = models.CharField(
        "CNPJ",
        max_length=14,
        unique=True,
        validators=[RegexValidator(r"^[0-9]{14}$", "Informe 14 dígitos numéricos.")],
    )


class Contract(NamedRecord):
    supplier = models.ForeignKey(Supplier, on_delete=models.PROTECT)
    department = models.ForeignKey(Department, on_delete=models.PROTECT)
    manager = models.CharField(max_length=150, blank=True)
    inspector = models.CharField(max_length=150, blank=True)
    status = models.CharField(
        max_length=12,
        choices=[
            ("DRAFT", "Em preparação"),
            ("ACTIVE", "Vigente"),
            ("SUSPENDED", "Suspenso"),
            ("CLOSED", "Encerrado"),
            ("CANCELLED", "Cancelado"),
        ],
        default="DRAFT",
    )
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    original_value = models.DecimalField(
        max_digits=18, decimal_places=2, default=0, validators=[MinValueValidator(0)]
    )
    # Carteiras serão vinculadas por rateios versionados na fase financeira.


class DepartmentAccess(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    department = models.ForeignKey(Department, on_delete=models.CASCADE)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "department"], name="unique_department_access"
            )
        ]


class CostCenter(NamedRecord):
    department = models.ForeignKey(Department, on_delete=models.PROTECT)


class AuditEvent(models.Model):
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    action = models.CharField(max_length=30)
    resource = models.CharField(max_length=100)
    object_id = models.CharField(max_length=40)
    before = models.JSONField(default=dict)
    after = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
