from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError, PermissionDenied
from apps.finance.access import require_departments
from apps.finance.services import audit
from .models import Answer, Evaluation, Invitation


@transaction.atomic
def submit_evaluation(*, actor, invitation, answers, comments):
    invitation = (
        Invitation.objects.select_for_update()
        .select_related("cycle", "contract")
        .get(pk=invitation.pk)
    )
    if invitation.user_id != actor.pk:
        raise PermissionDenied(
            "A avaliação deve ser preenchida pelo colaborador convidado."
        )
    require_departments(actor, {invitation.contract.department_id})
    cycle = invitation.cycle
    today = timezone.localdate()
    if not cycle.active or not cycle.opens <= today <= cycle.closes:
        raise ValidationError("Ciclo de avaliação encerrado ou ainda não aberto.")
    if Evaluation.objects.filter(invitation=invitation).exists():
        raise ValidationError("Esta avaliação já foi enviada.")
    expected = set(invitation.criteria.values_list("pk", flat=True))
    provided = [answer["criterion"] for answer in answers]
    if not expected or len(provided) != len(set(provided)) or set(provided) != expected:
        raise ValidationError(
            "Responda todos os critérios do convite, usando Não sei avaliar quando necessário."
        )
    for answer in answers:
        if answer["score"] is not None and answer["score"] not in range(1, 6):
            raise ValidationError(
                "Notas devem estar entre 1 e 5 ou ser Não sei avaliar."
            )
    evaluation = Evaluation.objects.create(invitation=invitation, **comments)
    Answer.objects.bulk_create(
        [
            Answer(evaluation=evaluation, criterion_id=a["criterion"], score=a["score"])
            for a in answers
        ]
    )
    audit(actor, "submit_evaluation", evaluation)
    return evaluation
