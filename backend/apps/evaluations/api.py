from django.db import transaction
from rest_framework import serializers, viewsets
from rest_framework.exceptions import PermissionDenied
from apps.finance.access import department_ids, require_departments
from apps.finance.services import audit
from apps.registry.api import ScopedModelPermissions
from .models import ActionPlan, Cycle, Evaluation, Invitation
from .services import submit_evaluation


class CycleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Cycle
        fields = "__all__"

    def validate(self, data):
        if data.get("opens") and data.get("closes") and data["closes"] < data["opens"]:
            raise serializers.ValidationError("Período inválido.")
        return data


class CycleViewSet(viewsets.ModelViewSet):
    queryset = Cycle.objects.all()
    serializer_class = CycleSerializer
    permission_classes = [ScopedModelPermissions]
    http_method_names = ["get", "post", "head", "options"]


class InvitationSerializer(serializers.ModelSerializer):
    contract_name = serializers.CharField(source="contract.name", read_only=True)
    cycle_label = serializers.SerializerMethodField()
    criteria_detail = serializers.SerializerMethodField()
    completed = serializers.SerializerMethodField()

    class Meta:
        model = Invitation
        fields = "__all__"

    def get_cycle_label(self, obj) -> str:
        return f"{obj.cycle.year} · {obj.cycle.quarter}º trimestre"

    def get_criteria_detail(self, obj) -> list[dict]:
        return list(obj.criteria.values("id", "name", "version"))

    def get_completed(self, obj) -> bool:
        return Evaluation.objects.filter(invitation=obj).exists()


class InvitationViewSet(viewsets.ModelViewSet):
    queryset = (
        Invitation.objects.select_related("contract", "cycle")
        .prefetch_related("criteria")
        .order_by("-pk")
    )
    serializer_class = InvitationSerializer
    http_method_names = ["get", "post", "head", "options"]

    def get_queryset(self):
        query = super().get_queryset()
        user = self.request.user
        if self.request.method == "GET":
            query = query.filter(user=user)
        if not user.is_superuser:
            query = query.filter(contract__department_id__in=department_ids(user))
        return query

    @transaction.atomic
    def perform_create(self, serializer):
        user = self.request.user
        if not user.has_perm("evaluations.add_invitation"):
            raise PermissionDenied("Sem permissão para convidar avaliadores.")
        data = serializer.validated_data
        require_departments(user, {data["contract"].department_id})
        require_departments(data["user"], {data["contract"].department_id})
        if not data["criteria"]:
            raise serializers.ValidationError("Defina os critérios do convite.")
        obj = serializer.save()
        audit(user, "invite", obj)


class AnswerInput(serializers.Serializer):
    criterion = serializers.IntegerField(min_value=1)
    score = serializers.IntegerField(min_value=1, max_value=5, allow_null=True)


class EvaluationSerializer(serializers.ModelSerializer):
    answers = AnswerInput(many=True, write_only=True)
    scores = serializers.SerializerMethodField()

    class Meta:
        model = Evaluation
        fields = "__all__"
        read_only_fields = ["submitted_at"]
        validators = []

    def get_scores(self, obj) -> list[dict]:
        return list(obj.answers.values("criterion_id", "score"))

    def create(self, data):
        return submit_evaluation(
            actor=self.context["request"].user,
            invitation=data.pop("invitation"),
            answers=data.pop("answers"),
            comments=data,
        )


class EvaluationViewSet(viewsets.ModelViewSet):
    queryset = Evaluation.objects.select_related("invitation__contract").order_by(
        "-submitted_at", "-pk"
    )
    serializer_class = EvaluationSerializer
    http_method_names = ["get", "post", "head", "options"]

    def get_queryset(self):
        query = super().get_queryset()
        user = self.request.user
        if not user.is_superuser:
            query = query.filter(
                invitation__contract__department_id__in=department_ids(user)
            )
        if not user.has_perm("evaluations.view_individual"):
            query = query.filter(invitation__user=user)
        return query


class PlanSerializer(serializers.ModelSerializer):
    class Meta:
        model = ActionPlan
        fields = "__all__"
        read_only_fields = ["created_by"]

    def validate(self, data):
        contract = data.get("contract", getattr(self.instance, "contract", None))
        require_departments(self.context["request"].user, {contract.department_id})
        return data


class PlanViewSet(viewsets.ModelViewSet):
    queryset = ActionPlan.objects.all().order_by("due_date", "pk")
    serializer_class = PlanSerializer
    permission_classes = [ScopedModelPermissions]
    http_method_names = ["get", "post", "patch", "head", "options"]

    def get_queryset(self):
        query = super().get_queryset()
        return (
            query
            if self.request.user.is_superuser
            else query.filter(
                contract__department_id__in=department_ids(self.request.user)
            )
        )

    def perform_create(self, serializer):
        obj = serializer.save(created_by=self.request.user)
        audit(self.request.user, "create", obj)

    def perform_update(self, serializer):
        obj = serializer.save()
        audit(self.request.user, "update", obj)
