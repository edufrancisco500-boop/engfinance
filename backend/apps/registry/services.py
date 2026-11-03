from django.db import transaction
from .models import AuditEvent


def save_record(*, serializer, actor, action):
    """Cadastro e histórico são persistidos juntos; sem regras financeiras nesta fase."""
    with transaction.atomic():
        instance = serializer.instance
        if instance is not None:
            # Recarrega após bloqueio para registrar o estado realmente substituído.
            serializer.instance = (
                type(instance).objects.select_for_update().get(pk=instance.pk)
            )
            before = dict(type(serializer)(serializer.instance).data)
        else:
            before = {}
        instance = serializer.save()
        from .models import Department, DepartmentAccess

        if isinstance(instance, Department) and action == "create":
            DepartmentAccess.objects.get_or_create(user=actor, department=instance)
        AuditEvent.objects.create(
            actor=actor,
            action=action,
            resource=instance._meta.label,
            object_id=str(instance.pk),
            before=before,
            after=dict(type(serializer)(instance).data),
        )
        return instance
