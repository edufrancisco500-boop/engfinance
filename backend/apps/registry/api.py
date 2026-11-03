from rest_framework import permissions, serializers, viewsets
from .models import (
    Contract,
    CostCenter,
    Department,
    DepartmentAccess,
    Portfolio,
    Project,
    Supplier,
    Coordination,
)
from .services import save_record


class ScopedModelPermissions(permissions.DjangoModelPermissions):
    perms_map = {
        **permissions.DjangoModelPermissions.perms_map,
        "GET": ["%(app_label)s.view_%(model_name)s"],
    }


def serializer_for(model):
    class RecordSerializer(serializers.ModelSerializer):
        class Meta:
            fields = "__all__"
            read_only_fields = ["id", "created_at"]

        def get_current_value(self, obj) -> str:
            from apps.finance.services import contract_value

            return str(contract_value(obj))

        def validate(self, attrs):
            user = self.context["request"].user
            department = attrs.get(
                "department", getattr(self.instance, "department", None)
            )
            if (
                department
                and not user.is_superuser
                and not DepartmentAccess.objects.filter(
                    user=user, department=department
                ).exists()
            ):
                raise serializers.ValidationError(
                    "Gerência fora do seu escopo de acesso."
                )
            start = attrs.get("start_date", getattr(self.instance, "start_date", None))
            end = attrs.get("end_date", getattr(self.instance, "end_date", None))
            if start and end and end < start:
                raise serializers.ValidationError(
                    "Conclusão não pode ser anterior ao início."
                )
            coordination = attrs.get(
                "coordination", getattr(self.instance, "coordination", None)
            )
            if (
                coordination
                and department
                and coordination.department_id != department.pk
            ):
                raise serializers.ValidationError(
                    "Coordenação deve pertencer à gerência do projeto."
                )
            if (
                self.instance
                and model is Coordination
                and "department" in attrs
                and attrs["department"].pk != self.instance.department_id
                and self.instance.project_set.exists()
            ):
                raise serializers.ValidationError(
                    "Coordenação vinculada a projetos não pode mudar de gerência."
                )
            if (
                self.instance
                and model is Project
                and "category" in attrs
                and attrs["category"] != self.instance.category
            ):
                from apps.finance.models import Allocation

                if Allocation.objects.filter(project=self.instance).exists():
                    raise serializers.ValidationError(
                        "Projeto com histórico financeiro: categoria exige reclassificação formal."
                    )
            if self.instance and model is Contract:
                changed = any(
                    k in attrs and attrs[k] != getattr(self.instance, k)
                    for k in ("original_value", "department", "supplier")
                )
                if changed and (
                    self.instance.financial_documents.exists()
                    or self.instance.fundings.exists()
                    or self.instance.amendments.exists()
                ):
                    raise serializers.ValidationError(
                        "Contrato com histórico financeiro: use aditivos e processos formais para alterações."
                    )
            if (
                self.instance
                and model in (Portfolio, Project, CostCenter)
                and "department" in attrs
                and attrs["department"].pk != self.instance.department_id
            ):
                from apps.finance.models import Budget, Allocation

                used = (
                    Budget.objects.filter(portfolio=self.instance).exists()
                    if model is Portfolio
                    else Allocation.objects.filter(
                        **{
                            "project"
                            if model is Project
                            else "cost_center": self.instance
                        }
                    ).exists()
                )
                if used:
                    raise serializers.ValidationError(
                        "Recurso com histórico financeiro não pode mudar de gerência."
                    )
            return attrs

    RecordSerializer.Meta.model = model
    if model is Contract:
        RecordSerializer._declared_fields["current_value"] = (
            serializers.SerializerMethodField()
        )
    RecordSerializer.__name__ = f"{model.__name__}Serializer"
    return RecordSerializer


def viewset_for(model):
    class RecordViewSet(viewsets.ModelViewSet):
        queryset = model.objects.all()
        serializer_class = serializer_for(model)
        permission_classes = [ScopedModelPermissions]
        http_method_names = ["get", "post", "put", "patch", "head", "options"]

        def get_queryset(self):
            query = super().get_queryset()
            if self.request.user.is_superuser:
                return query
            ids = DepartmentAccess.objects.filter(user=self.request.user).values(
                "department_id"
            )
            if model is Department:
                return query.filter(pk__in=ids)
            if model is Supplier:
                # Fornecedores são cadastro compartilhado; leitura exige permissão de modelo.
                return query
            return query.filter(department_id__in=ids)

        def save_audited(self, serializer, action):
            save_record(serializer=serializer, actor=self.request.user, action=action)

        def perform_create(self, serializer):
            self.save_audited(serializer, "create")

        def perform_update(self, serializer):
            self.save_audited(serializer, "update")

    return RecordViewSet


RESOURCES = {
    "departments": Department,
    "portfolios": Portfolio,
    "projects": Project,
    "suppliers": Supplier,
    "contracts": Contract,
    "cost-centers": CostCenter,
    "coordinations": Coordination,
}
