from django.conf import settings
from django.db import models
from django.db.models import Q


class Cycle(models.Model):
    year = models.PositiveIntegerField()
    quarter = models.PositiveSmallIntegerField()
    opens = models.DateField()
    closes = models.DateField()
    active = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["year", "quarter"], name="unique_evaluation_quarter"
            ),
            models.CheckConstraint(
                condition=Q(quarter__gte=1, quarter__lte=4), name="valid_quarter"
            ),
            models.CheckConstraint(
                condition=Q(closes__gte=models.F("opens")), name="valid_cycle_dates"
            ),
        ]
        ordering = ["-year", "-quarter"]


class Criterion(models.Model):
    name = models.CharField(max_length=120)
    version = models.PositiveIntegerField(default=1)
    active = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["name", "version"], name="unique_criterion_version"
            )
        ]


class Invitation(models.Model):
    cycle = models.ForeignKey(Cycle, on_delete=models.PROTECT)
    contract = models.ForeignKey("registry.Contract", on_delete=models.PROTECT)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    criteria = models.ManyToManyField(Criterion)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["cycle", "contract", "user"],
                name="unique_evaluation_invitation",
            )
        ]


class Evaluation(models.Model):
    invitation = models.OneToOneField(
        Invitation, on_delete=models.PROTECT, related_name="evaluation"
    )
    positives = models.TextField(blank=True)
    negatives = models.TextField(blank=True)
    problems = models.TextField(blank=True)
    suggestions = models.TextField(blank=True)
    continuity = models.TextField(blank=True)
    submitted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        permissions = [
            ("view_individual", "Consultar avaliações individuais restritas"),
            ("view_results", "Consultar resultados agregados das avaliações"),
        ]


class Answer(models.Model):
    evaluation = models.ForeignKey(
        Evaluation, on_delete=models.PROTECT, related_name="answers"
    )
    criterion = models.ForeignKey(Criterion, on_delete=models.PROTECT)
    score = models.PositiveSmallIntegerField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["evaluation", "criterion"], name="unique_criterion_answer"
            ),
            models.CheckConstraint(
                condition=Q(score__isnull=True) | Q(score__gte=1, score__lte=5),
                name="valid_evaluation_score",
            ),
        ]


class ActionPlan(models.Model):
    contract = models.ForeignKey("registry.Contract", on_delete=models.PROTECT)
    title = models.CharField(max_length=180)
    description = models.TextField(blank=True)
    responsible = models.CharField(max_length=150)
    due_date = models.DateField()
    status = models.CharField(
        max_length=12,
        choices=[
            ("OPEN", "Aberto"),
            ("PROGRESS", "Em andamento"),
            ("DONE", "Concluído"),
        ],
        default="OPEN",
    )
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
